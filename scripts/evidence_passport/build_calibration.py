"""
Evidence Passport / Selective Prediction - Step 1: calibration.

Production Model 1 is trained on 100% of the labeled data (no held-out set),
so its raw softmax "confidence" has never been checked against how often it's
actually right. This script produces that check: train the identical
pipeline on a 70% held-out split, score the other 30%, and bin predictions
by confidence to get an EMPIRICAL reliability curve (not a guessed one).

Also produces a risk-coverage curve (accuracy vs. how much of the test set
you're willing to answer for), used to pick a defensible abstention
threshold for selective prediction.

Output: processed/evidence_passport/calibration_bins.json,
        processed/evidence_passport/risk_coverage.json,
        processed/evidence_passport/thresholds.json
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
from train_eval_severity_model import FEATURE_COLS, load_dataset, make_model  # noqa: E402

PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "evidence_passport"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]


def main() -> None:
    print("Loading full production dataset...")
    df = load_dataset(PROCESSED_DIR / "polyguard_all_drugs_severity_pairs.csv")
    print(f"{len(df):,} rows")

    train_df, test_df = train_test_split(
        df, test_size=0.30, random_state=RANDOM_STATE, stratify=df["severity"]
    )
    print("Training held-out calibration model (identical pipeline to production Model 1)...")
    model = make_model()
    model.fit(train_df[FEATURE_COLS], train_df["severity"])

    proba = model.predict_proba(test_df[FEATURE_COLS])
    classes = list(model.classes_)
    y_true = test_df["severity"].to_numpy()
    confidence = proba.max(axis=1)
    top2 = np.sort(proba, axis=1)[:, -2:]
    margin = top2[:, 1] - top2[:, 0]
    y_pred = np.array([classes[i] for i in proba.argmax(axis=1)])
    correct = (y_pred == y_true)

    # --- Calibration bins: fixed-width confidence bins, empirical accuracy per bin ---
    bin_edges = np.arange(0.30, 1.01, 0.05)  # 3-class softmax max is always >= 1/3
    bin_idx = np.digitize(confidence, bin_edges) - 1
    bins = []
    for b in range(len(bin_edges) - 1):
        mask = bin_idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        bins.append({
            "confidence_low": round(float(bin_edges[b]), 2),
            "confidence_high": round(float(bin_edges[b + 1]), 2),
            "n": n,
            "empirical_accuracy": round(float(correct[mask].mean()), 4),
        })
    with open(OUT_DIR / "calibration_bins.json", "w", encoding="utf-8") as f:
        json.dump(bins, f, indent=2)
    print("Calibration bins:")
    for b in bins:
        print(f"  [{b['confidence_low']:.2f}-{b['confidence_high']:.2f}) n={b['n']:>5}  empirical_accuracy={b['empirical_accuracy']:.3f}")

    # --- Risk-coverage curve: sort by confidence desc, accuracy at each coverage level ---
    order = np.argsort(-confidence)
    correct_sorted = correct[order]
    coverage_levels = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.5, 0.4, 0.3]
    risk_coverage = []
    n_total = len(correct_sorted)
    for cov in coverage_levels:
        k = max(1, int(n_total * cov))
        acc = float(correct_sorted[:k].mean())
        risk_coverage.append({"coverage": cov, "n": k, "accuracy": round(acc, 4)})
    with open(OUT_DIR / "risk_coverage.json", "w", encoding="utf-8") as f:
        json.dump(risk_coverage, f, indent=2)
    print("\nRisk-coverage curve:")
    for r in risk_coverage:
        print(f"  coverage={r['coverage']:.2f}  n={r['n']:>5}  accuracy={r['accuracy']:.3f}")

    # --- Pick a defensible abstention threshold ---
    # Find the lowest confidence value such that, among predictions AT OR ABOVE it,
    # empirical accuracy is comfortably above the majority-class baseline for this
    # test set (a prediction that's no better than "always guess Moderate" isn't
    # worth presenting as a confident answer).
    majority_acc = float((y_true == pd.Series(y_true).value_counts().idxmax()).mean())
    target_floor = max(0.55, majority_acc)  # never abstain-threshold below 55% empirical accuracy
    sorted_conf = confidence[order]
    running_correct = np.cumsum(correct_sorted) / np.arange(1, n_total + 1)
    # last index (by confidence-descending order) where cumulative accuracy still clears the floor
    ok = np.where(running_correct >= target_floor)[0]
    if len(ok) > 0:
        cutoff_idx = ok[-1]
        confidence_threshold = float(sorted_conf[cutoff_idx])
        coverage_at_threshold = float((cutoff_idx + 1) / n_total)
    else:
        confidence_threshold = 1.01  # nothing clears the floor -> abstain on everything undocumented
        coverage_at_threshold = 0.0

    # Margin threshold: 10th percentile of margin among CORRECT high-confidence predictions,
    # i.e. a sanity floor below which the model is meaningfully unsure between top-2 classes.
    margin_threshold = float(np.percentile(margin, 15))

    thresholds = {
        "majority_class_baseline_accuracy_on_heldout": round(majority_acc, 4),
        "target_reliability_floor": round(target_floor, 4),
        "confidence_threshold": round(confidence_threshold, 4),
        "coverage_at_confidence_threshold": round(coverage_at_threshold, 4),
        "margin_threshold": round(margin_threshold, 4),
        "note": (
            "abstain (for undocumented pairs only) when confidence < confidence_threshold "
            "OR margin < margin_threshold. Documented pairs are never abstained on - they "
            "have a real labeled example, not just a model guess."
        ),
    }
    with open(OUT_DIR / "thresholds.json", "w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)
    print(f"\nChosen thresholds: {json.dumps(thresholds, indent=2)}")


if __name__ == "__main__":
    main()
