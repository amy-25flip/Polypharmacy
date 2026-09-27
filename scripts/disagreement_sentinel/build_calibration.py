"""
Model Disagreement Sentinel - build step.

Repurposes Model 2 (chemistry, a documented negative result on its own - see
CHEMISTRY_MODEL_FINDINGS.md) as an independent second opinion alongside
Model 1 (production). The two models are trained on completely different
signals (drug-name text vs. Morgan-fingerprint chemistry), so when they
sharply disagree about a pair's severity, that disagreement is informative
even though Model 2 alone is worse than Model 1.

This script:
  1. Trains Model 1 (TF-IDF+LogReg) and Model 2 (chemistry) identically-split
     (70/30, same rows - the chemistry-coverage subset) to measure, on a real
     held-out set, whether disagreement between them predicts Model 1 being
     wrong. That's the ONLY thing that justifies shipping this feature - if
     disagreement doesn't correlate with error, it's not worth building.
  2. Trains a PRODUCTION copy of Model 2 on 100% of the chemistry-coverage
     data (same idea as Model 1 production: use everything for live scoring;
     the 70/30 split above is only used to derive the calibration curve).

Output: processed/disagreement_sentinel/model2_chemistry_pipeline.joblib
        (production, 100%-trained)
        processed/disagreement_sentinel/disagreement_calibration.json
        (held-out bins: disagreement level -> Model 1 empirical accuracy)
        processed/disagreement_sentinel/fingerprint_cache.json
        (drug_name_norm -> list[int] Morgan bit indices, for live inference)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from train_eval_chemistry_model import (  # noqa: E402
    N_BITS,
    SEVERITY_ORDER,
    build_dataset,
    load_fingerprint_lookup,
    make_model,
)
from train_eval_severity_model import FEATURE_COLS  # noqa: E402
from train_eval_severity_model import make_model as make_model1  # noqa: E402

PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "disagreement_sentinel"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42

PAIRS_CSV = PROCESSED_DIR / "polyguard_all_drugs_severity_pairs.csv"
SMILES_CACHE = PROCESSED_DIR / "drug_name_smiles_cache.csv"


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence between two categorical distributions."""
    m = 0.5 * (p + q)
    def kl(a, b):
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def main() -> None:
    print("Building chemistry-coverage dataset (reusing Model 2's build_dataset)...")
    kept_df, X_chem, total_pairs = build_dataset(PAIRS_CSV, SMILES_CACHE)
    print(f"Chemistry coverage: {len(kept_df):,} / {total_pairs:,} pairs")

    # Model 1's text-based feature needs drug_a/drug_b + disease flags on the SAME rows.
    # kept_df already carries drug_a/drug_b from the original CSV (build_dataset only filters
    # rows, it doesn't drop columns), so derive Model 1's pair_text feature directly from it -
    # this guarantees Model 1 and Model 2 are scored on the exact same rows in the exact same order.
    m1_rows = kept_df.copy()
    for col in ["disease_diabetes", "disease_ckd", "disease_heart_failure", "disease_hypertension"]:
        m1_rows[col] = 0
    pair_parts = np.sort(m1_rows[["drug_a", "drug_b"]].astype(str).values, axis=1)
    m1_rows["pair_text"] = pair_parts[:, 0] + " [DRUG_PAIR] " + pair_parts[:, 1] + " [DISEASE_SCOPE] "

    y = kept_df["severity"].to_numpy()
    idx_train, idx_test = train_test_split(
        np.arange(len(kept_df)), test_size=0.30, random_state=RANDOM_STATE, stratify=y
    )

    print("Training held-out Model 1 (text) on chemistry-coverage subset...")
    model1_cal = make_model1()
    model1_cal.fit(m1_rows.iloc[idx_train][FEATURE_COLS], m1_rows.iloc[idx_train]["severity"])
    proba1 = model1_cal.predict_proba(m1_rows.iloc[idx_test][FEATURE_COLS])
    classes1 = list(model1_cal.classes_)

    print("Training held-out Model 2 (chemistry) on the identical split...")
    model2_cal = make_model()
    model2_cal.fit(X_chem[idx_train], y[idx_train])
    proba2 = model2_cal.predict_proba(X_chem[idx_test])
    classes2 = list(model2_cal.classes_)

    # Align both probability vectors to the same class order.
    order = SEVERITY_ORDER
    proba1_aligned = np.stack([proba1[:, classes1.index(c)] for c in order], axis=1)
    proba2_aligned = np.stack([proba2[:, classes2.index(c)] for c in order], axis=1)

    y_test = y[idx_test]
    pred1 = np.array([order[i] for i in proba1_aligned.argmax(axis=1)])
    correct1 = (pred1 == y_test)

    disagreement = np.array([js_divergence(p1, p2) for p1, p2 in zip(proba1_aligned, proba2_aligned)])
    top_class_mismatch = proba1_aligned.argmax(axis=1) != proba2_aligned.argmax(axis=1)

    # Bin by disagreement (JS divergence, 0=identical distributions, up to ~1=maximally different)
    bin_edges = np.array([0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 1.01])
    bin_idx = np.digitize(disagreement, bin_edges) - 1
    bins = []
    for b in range(len(bin_edges) - 1):
        mask = bin_idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        bins.append({
            "js_divergence_low": round(float(bin_edges[b]), 3),
            "js_divergence_high": round(float(bin_edges[b + 1]), 3),
            "n": n,
            "model1_empirical_accuracy": round(float(correct1[mask].mean()), 4),
            "top_class_mismatch_rate": round(float(top_class_mismatch[mask].mean()), 4),
        })

    overall_acc = float(correct1.mean())
    print(f"\nOverall Model 1 accuracy on this held-out set: {overall_acc:.4f}")
    print("Disagreement bins (JS divergence -> Model 1 empirical accuracy):")
    for b in bins:
        print(f"  [{b['js_divergence_low']:.3f}-{b['js_divergence_high']:.3f})  n={b['n']:>5}  "
              f"Model1_acc={b['model1_empirical_accuracy']:.3f}  top_class_mismatch={b['top_class_mismatch_rate']:.3f}")

    corr = float(np.corrcoef(disagreement, ~correct1)[0, 1])
    print(f"\nPoint-biserial correlation(disagreement, Model1_error): {corr:.4f}  "
          f"({'disagreement predicts error - feature justified' if corr > 0.05 else 'weak/no signal - reconsider shipping this'})")

    with open(OUT_DIR / "disagreement_calibration.json", "w", encoding="utf-8") as f:
        json.dump({
            "overall_model1_accuracy_on_this_heldout": round(overall_acc, 4),
            "correlation_disagreement_vs_error": round(corr, 4),
            "bins": bins,
        }, f, indent=2)

    # --- Production Model 2: train on 100% of chemistry-coverage data ---
    print("\nTraining PRODUCTION Model 2 (chemistry) on 100% of chemistry-coverage data...")
    model2_prod = make_model()
    model2_prod.fit(X_chem, y)
    import joblib
    joblib.dump(model2_prod, OUT_DIR / "model2_chemistry_pipeline.joblib")
    print(f"Saved production Model 2 to {OUT_DIR / 'model2_chemistry_pipeline.joblib'}")

    # --- Fingerprint cache for live inference (drug_name_norm -> Morgan bit indices) ---
    print("Building fingerprint cache for live inference...")
    fingerprints = load_fingerprint_lookup(SMILES_CACHE)
    fp_cache = {name: np.nonzero(bits)[0].tolist() for name, bits in fingerprints.items()}
    with open(OUT_DIR / "fingerprint_cache.json", "w", encoding="utf-8") as f:
        json.dump({"n_bits": N_BITS, "fingerprints": fp_cache}, f)
    print(f"Saved fingerprint cache ({len(fp_cache)} drugs) to {OUT_DIR / 'fingerprint_cache.json'}")


if __name__ == "__main__":
    main()
