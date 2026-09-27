from __future__ import annotations

import itertools
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from evidence_passport import EvidencePassportEngine
from explainability import ExplainabilityEngine
from hoddi_model import HoddiInferenceModel, build_fingerprint_lookup

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

    result["evidence_passport"] = evidence_passport_engine.build(
        drug_a_norm=normalize(drug_a),
        drug_b_norm=normalize(drug_b),
        confidence=confidence,
        margin=margin,
        is_documented=is_documented,
        has_mechanism_evidence=explanation["has_explanation"],
        has_indirect_evidence=bool(explanation["supporting_evidence"]) and not explanation["has_explanation"],
    )

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

    results = sorted(prefix_hits) + sorted(substring_hits)
    if len(results) < 8:
        fuzzy_matches = process.extract(q, DRUG_VOCAB, scorer=fuzz.WRatio, limit=8)
        for name, score, _ in fuzzy_matches:
            if score >= 60 and name not in results:
                results.append(name)

    return results[:8]


@app.post("/api/check")
def check(payload: CheckRequest):
    entered_names = [d.strip() for d in payload.drugs if d.strip()]
    matched = [d for d in entered_names if d in DRUG_VOCAB_SET]
    unmatched = [d for d in entered_names if d not in DRUG_VOCAB_SET]

    regimen = predict_regimen(matched) if len(matched) >= 2 else {"overall_severity": None, "pairs": []}
    hoddi_result = predict_hoddi_signal(matched) if len(matched) >= 3 else None

    return {
        "entered": entered_names,
        "matched": matched,
        "unmatched": unmatched,
        "regimen": regimen,
        "combination_signal": hoddi_result,
    }
