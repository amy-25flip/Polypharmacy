from __future__ import annotations

import itertools
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from brand_names import BRAND_NAMES, lookup_brand_matches
from conformal import ConformalEngine
from disagreement_sentinel import DisagreementSentinel
from evidence_passport import EvidencePassportEngine
from explainability import ExplainabilityEngine
from hoddi_model import HoddiInferenceModel, build_fingerprint_lookup
from prescription_scan import scan_prescription
from subset_certificate import build_certificate

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Robust search for processed directory across local, Docker, and Render paths
def resolve_dir(env_var: str, default_name: str) -> Path:
    if os.environ.get(env_var):
        return Path(os.environ[env_var])
    candidates = [
        PROJECT_ROOT / default_name,
        Path(__file__).resolve().parent / default_name,
        Path(default_name),
        Path("..") / default_name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

PROCESSED_DIR = resolve_dir("POLYGUARD_PROCESSED_DIR", "processed")
DATASETS_DIR = resolve_dir("POLYGUARD_DATASETS_DIR", "Datasets")

SEVERITY_RANK = {"Minor": 0, "Moderate": 1, "Major": 2}

app = FastAPI(title="PolyGuard API")

_allowed_origins_env = os.environ.get(
    "POLYGUARD_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://polyguard-frontend.onrender.com",
)
_allowed_origins = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# --- Load everything once at startup ---
print("Loading Model 1 (pairwise severity)...")
model1 = joblib.load(PROCESSED_DIR / "model1_severity_pipeline.joblib")

with open(PROCESSED_DIR / "drug_vocabulary.json", encoding="utf-8") as f:
    DRUG_VOCAB: list[str] = json.load(f)
DRUG_VOCAB_SET = set(DRUG_VOCAB)

with open(PROCESSED_DIR / "drug_name_to_drugbank_id.json", encoding="utf-8") as f:
    NAME_TO_DRUGBANK_ID: dict[str, str] = json.load(f)

print("Loading Model 3 (HODDI DeepSets, drugs+context, no AE)...")
with open(PROCESSED_DIR / "hoddi_vocabs.json", encoding="utf-8") as f:
    HODDI_VOCABS = json.load(f)
HODDI_FP_LOOKUP = build_fingerprint_lookup(DATASETS_DIR / "DrugBankID2SMILES.csv")
hoddi_model = HoddiInferenceModel(HODDI_VOCABS)
hoddi_model.load_state_dict(torch.load(PROCESSED_DIR / "hoddi_deepsets_final_model.pt", map_location="cpu"))
hoddi_model.eval()

print("Loading explainability engine (Hetionet knowledge-graph evidence)...")
explain_engine = ExplainabilityEngine(PROCESSED_DIR / "explainability_data.json")


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


print("Loading documented-pairs index (which pairs actually have a real DDInter label)...")
with open(PROCESSED_DIR / "documented_pairs.json", encoding="utf-8") as f:
    DOCUMENTED_PAIRS: set[str] = set(json.load(f))

print("Loading Evidence Passport engine (calibration + selective prediction)...")
evidence_passport_engine = EvidencePassportEngine(PROCESSED_DIR / "evidence_passport")

print("Loading Model Disagreement Sentinel (Model 1 vs. chemistry-model second opinion)...")
disagreement_sentinel = DisagreementSentinel(PROCESSED_DIR / "disagreement_sentinel")

print("Loading Conformal Severity Sets engine (calibrated set-valued predictions)...")
conformal_engine = ConformalEngine(PROCESSED_DIR / "conformal")

print("Loading model-transparency page data...")
print(f"Loading Indian brand-name index ({len(BRAND_NAMES)} curated names)...")
print(
    "Prescription scanning available when GEMINI_API_KEY is set "
    f"({'configured' if os.environ.get('GEMINI_API_KEY') else 'currently unconfigured'})."
)


def _load_json(path: Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


TRANSPARENCY_DATA = {
    "model1_calibration": {
        "bins": _load_json(PROCESSED_DIR / "evidence_passport" / "calibration_bins.json"),
        "risk_coverage": _load_json(PROCESSED_DIR / "evidence_passport" / "risk_coverage.json"),
        "thresholds": _load_json(PROCESSED_DIR / "evidence_passport" / "thresholds.json"),
        "method": (
            "Model 1's exact pipeline retrained on a 70% held-out split of the full "
            "130,422-pair production dataset, scored on the other 30% - never on data "
            "the production model was itself trained on."
        ),
    },
    "conformal_sets": {
        "eval": _load_json(PROCESSED_DIR / "conformal" / "eval.json"),
        "method": (
            "Mondrian (class-conditional) split conformal prediction. Fit on a calibration "
            "fold (15% of data) genuinely separate from the reported test fold (another 15%) "
            "- coverage numbers below are not circular."
        ),
    },
    "disagreement_sentinel": {
        "calibration": _load_json(PROCESSED_DIR / "disagreement_sentinel" / "disagreement_calibration.json"),
        "method": (
            "Model 1 (text) and Model 2 (chemistry) trained on an identical 70/30 split of "
            "the chemistry-coverage subset (48,991 pairs). Disagreement measured as "
            "Jensen-Shannon divergence between their predicted probability distributions on "
            "the held-out 30%, binned against how often Model 1 was actually wrong."
        ),
    },
    "model_comparison": {
        "note": "All figures from identical-subset, identical-split head-to-head evaluations - see "
                "CHEMISTRY_MODEL_FINDINGS.md and MODEL4_GNN_FINDINGS.md for full methodology.",
        "rows": [
            {"model": "Majority-class baseline", "standard_accuracy": 0.751, "standard_macro_f1": 0.286,
             "cold_start_accuracy": 0.758, "cold_start_macro_f1": 0.287, "status": "baseline"},
            {"model": "Model 1 - text (production)", "standard_accuracy": 0.739, "standard_macro_f1": 0.616,
             "cold_start_accuracy": 0.656, "cold_start_macro_f1": 0.530, "status": "shipped"},
            {"model": "Model 2 - chemistry (Morgan fingerprints)", "standard_accuracy": 0.771, "standard_macro_f1": 0.670,
             "cold_start_accuracy": 0.569, "cold_start_macro_f1": 0.437, "status": "negative_result"},
            {"model": "Hybrid - text + chemistry", "standard_accuracy": 0.776, "standard_macro_f1": 0.676,
             "cold_start_accuracy": 0.592, "cold_start_macro_f1": 0.456, "status": "negative_result"},
            {"model": "Model 4 - full GNN (GATv2 + KG embeddings + co-attention)", "standard_accuracy": 0.676,
             "standard_macro_f1": 0.593, "cold_start_accuracy": 0.487, "cold_start_macro_f1": 0.403,
             "status": "negative_result"},
        ],
        "finding": (
            "Every structure/graph-based approach tried beats the text baseline in-distribution "
            "(standard split) but loses on cold-start (genuinely unseen drugs) - the harder, more "
            "realistic test. DDI severity labels in this dataset correlate more with drug-name/"
            "pharmacologic-class lexical patterns than with molecular structure or knowledge-graph "
            "relationships, at this data scale. Model 1 (the simplest model) is what's deployed."
        ),
    },
    "dataset": {
        "total_documented_pairs": len(DOCUMENTED_PAIRS),
        "total_drugs": len(DRUG_VOCAB),
        "drugs_with_drugbank_id": len(NAME_TO_DRUGBANK_ID),
        "support_tiers": _load_json(PROCESSED_DIR / "evidence_passport" / "support_tiers.json"),
    },
}

print(f"Ready. {len(DRUG_VOCAB)} known drugs, {len(NAME_TO_DRUGBANK_ID)} with DrugBankID/HODDI support, "
      f"{len(DOCUMENTED_PAIRS)} documented pairs.")


def predict_pair(drug_a: str, drug_b: str) -> dict:
    row = pd.DataFrame(
        [
            {
                "pair_text": " [DRUG_PAIR] ".join(sorted([drug_a, drug_b])) + " [DISEASE_SCOPE] ",
                "disease_diabetes": 0,
                "disease_ckd": 0,
                "disease_heart_failure": 0,
                "disease_hypertension": 0,
            }
        ]
    )
    feature_cols = ["pair_text", "disease_diabetes", "disease_ckd", "disease_heart_failure", "disease_hypertension"]
    severity = model1.predict(row[feature_cols])[0]
    proba = model1.predict_proba(row[feature_cols])[0]
    model1_classes = list(model1.classes_)
    is_documented = "|".join(sorted((normalize(drug_a), normalize(drug_b)))) in DOCUMENTED_PAIRS
    confidence = float(np.max(proba))
    top2 = np.sort(proba)[-2:]
    margin = float(top2[1] - top2[0])
    result = {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "severity": severity,
        "confidence": round(confidence, 3),
        "is_documented": is_documented,
        "conformal_sets": conformal_engine.severity_sets(list(proba), model1_classes),
    }

    id_a = NAME_TO_DRUGBANK_ID.get(normalize(drug_a))
    id_b = NAME_TO_DRUGBANK_ID.get(normalize(drug_b))

    # Explainability is computed regardless of severity - the Evidence Passport
    # needs to know whether mechanism evidence exists even for a Minor prediction,
    # even though the full explanation panel is only shown to the user for
    # Moderate/Major (a display choice, not a data limitation).
    explanation = explain_engine.explain_pair(id_a, id_b)
    if severity in ("Moderate", "Major"):
        result["explanation"] = explanation

    passport = evidence_passport_engine.build(
        drug_a_norm=normalize(drug_a),
        drug_b_norm=normalize(drug_b),
        confidence=confidence,
        margin=margin,
        is_documented=is_documented,
        has_mechanism_evidence=explanation["has_explanation"],
        has_indirect_evidence=bool(explanation["supporting_evidence"]) and not explanation["has_explanation"],
    )

    # Model Disagreement Sentinel: an independent second opinion from Model 2
    # (chemistry) - only available for the ~38% of pairs where both drugs have
    # a resolved SMILES. Held-out testing showed this is a real, strong signal
    # (84.5% Model 1 accuracy when models agree, down to 13.3% when they sharply
    # disagree - see scripts/disagreement_sentinel/build_calibration.py), so a
    # high-disagreement, undocumented pair is forced to abstain even if Model 1's
    # own confidence looked fine - the confidence-only view was already shown to
    # be misleading in exactly this situation.
    agreement = disagreement_sentinel.score(normalize(drug_a), normalize(drug_b), proba, model1_classes)
    passport["cross_model_agreement"] = agreement
    if agreement and not is_documented and not passport["abstain"] and agreement["disagreement_level"] == "High":
        passport["abstain"] = True
        passport["abstain_reason"] = (
            f"The chemistry-based model disagrees sharply with this prediction "
            f"(severity: {agreement['chemistry_model_severity']}). Historically, when the two "
            f"independent models disagree this much, the primary model was only right "
            f"{agreement['model1_empirical_accuracy_at_this_disagreement']:.0%} of the time."
        )

    result["evidence_passport"] = passport

    if not is_documented:
        # No labeled example for this exact pair exists in the source data (DDInter
        # either never covers it, or only has it as an "Unknown"-severity row that
        # was correctly excluded from training). The severity above is the model
        # generalizing from other drugs' lexical patterns, not a documented fact -
        # and its confidence score does NOT reliably reflect that, so this has to
        # be surfaced explicitly rather than left implicit.
        result["undocumented_pair_notice"] = (
            "No documented interaction record exists for this exact drug pair in the "
            "reference database. This result is inferred from patterns in other drugs' "
            "names, not from a confirmed interaction record - treat it with extra caution "
            "and verify independently, regardless of the severity shown above."
        )

    return result


def predict_regimen(drug_names: list[str]) -> dict:
    pairs = [predict_pair(a, b) for a, b in itertools.combinations(drug_names, 2)]
    if not pairs:
        return {"overall_severity": None, "pairs": []}
    pairs_sorted = sorted(pairs, key=lambda p: (SEVERITY_RANK[p["severity"]], p["confidence"]), reverse=True)
    return {"overall_severity": pairs_sorted[0]["severity"], "pairs": pairs_sorted}


def predict_hoddi_signal(drug_names: list[str]) -> dict | None:
    drugbank_ids = [NAME_TO_DRUGBANK_ID.get(normalize(n)) for n in drug_names]
    resolved_ids = [d for d in drugbank_ids if d and d in HODDI_FP_LOOKUP]
    if len(resolved_ids) < 3:
        return None
    resolved_ids = resolved_ids[:5]  # model trained on sets of 3-5

    prob = hoddi_model.predict_proba(resolved_ids, HODDI_FP_LOOKUP)
    return {
        "drugs_used": len(resolved_ids),
        "drugs_total": len(drug_names),
        "probability": round(prob, 3),
        "elevated": prob >= 0.5,
    }


class CheckRequest(BaseModel):
    drugs: list[str]


@app.get("/api/health")
def health():
    return {"status": "ok", "known_drugs": len(DRUG_VOCAB)}


@app.get("/api/transparency")
def transparency():
    return TRANSPARENCY_DATA


@app.get("/api/drugs/search")
def search_drugs(q: str = ""):
    q = q.strip()
    if len(q) < 2:
        return []
    q_lower = q.lower()

    # Prefix and substring matches first (what a doctor typing the start of a
    # real drug name expects to see), then fuzzy/typo matches to fill the rest.
    prefix_hits = [name for name in DRUG_VOCAB if name.lower().startswith(q_lower)]
    substring_hits = [
        name for name in DRUG_VOCAB
        if q_lower in name.lower() and name not in prefix_hits
    ]

    direct_results = sorted(prefix_hits) + sorted(substring_hits)
    results = [{"name": name, "matched_via_brand": None} for name in direct_results]
    seen = set(direct_results)
    # Prefer a curated brand interpretation to coincidental typo matches. Direct
    # prefix/substring vocabulary hits still keep first place.
    for brand, generic_names in lookup_brand_matches(q):
        for name in generic_names:
            if name not in seen:
                results.append({"name": name, "matched_via_brand": brand})
                seen.add(name)

    if len(results) < 8:
        fuzzy_matches = process.extract(q, DRUG_VOCAB, scorer=fuzz.WRatio, limit=8)
        for name, score, _ in fuzzy_matches:
            if score >= 60 and name not in seen:
                results.append({"name": name, "matched_via_brand": None})
                seen.add(name)

    return results[:8]


@app.post("/api/prescriptions/scan")
async def scan_prescription_image(file: UploadFile = File(...)):
    content_type = file.content_type or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a prescription image file.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded prescription image is empty.")

    result = scan_prescription(image_bytes, content_type, DRUG_VOCAB, fuzz, process)
    if result.get("error"):
        return JSONResponse(status_code=503, content={"error": result["error"]})
    return result


@app.post("/api/check")
def check(payload: CheckRequest):
    entered_names = [d.strip() for d in payload.drugs if d.strip()]
    matched = [d for d in entered_names if d in DRUG_VOCAB_SET]
    unmatched = [d for d in entered_names if d not in DRUG_VOCAB_SET]

    regimen = predict_regimen(matched) if len(matched) >= 2 else {"overall_severity": None, "pairs": []}
    hoddi_result = predict_hoddi_signal(matched) if len(matched) >= 3 else None
    subset_cert = (
        build_certificate(matched, NAME_TO_DRUGBANK_ID, HODDI_FP_LOOKUP, hoddi_model, normalize)
        if len(matched) >= 4
        else None
    )

    return {
        "entered": entered_names,
        "matched": matched,
        "unmatched": unmatched,
        "regimen": regimen,
        "combination_signal": hoddi_result,
        "subset_certificate": subset_cert,
    }


# --- Optional single-origin static frontend serving ---
# On Render, the frontend is a SEPARATE static-hosting service (see render.yaml)
# and this directory never exists in the backend's deployment, so this block is
# a no-op there. It exists for self-hosting the whole app (backend + built
# frontend) as one process behind one tunnel/port - e.g. running this on your
# own machine with ngrok, where a single origin avoids CORS entirely. Build the
# frontend first (cd webapp/frontend && npm run build) for this to activate.
_FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    print(f"Serving built frontend from {_FRONTEND_DIST} (single-origin self-hosting mode).")
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Real static files (favicon, etc.) served directly; everything else
        # (including client-side routes like /model-card) falls back to
        # index.html so the SPA's own router can handle it.
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
