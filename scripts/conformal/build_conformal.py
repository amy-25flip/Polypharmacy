"""
Conformal Severity Sets - build step.

Upgrades a single forced severity label into a set-valued prediction with a
measurable coverage guarantee: "at 90% target coverage, the plausible
severities for this pair are {Moderate, Major}". Easy pairs get a singleton
set; genuinely ambiguous pairs get two or three labels - the set size itself
becomes an honest signal, instead of forcing one answer every time.

Method: split conformal prediction, Mondrian (class-conditional) so the
majority class (Moderate, ~74% of the data) doesn't buy good coverage at the
expense of the rare Major class - which is exactly the one you can't afford
to under-cover in a safety tool.

Uses a clean 3-way split (train 70% / calibrate 15% / test 15%, stratified,
seed 42) so the reported coverage numbers are from data the quantiles were
never fit on - not circular.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from train_eval_severity_model import FEATURE_COLS, load_dataset, make_model  # noqa: E402

PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "conformal"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
TARGET_COVERAGES = [0.80, 0.90, 0.95]


def mondrian_quantiles(proba: np.ndarray, y_true: np.ndarray, classes: list[str], target_coverage: float) -> dict[str, float]:
    """Per-class nonconformity quantile: threshold q_c such that including all
    classes with proba >= 1 - q_c covers the true label >= target_coverage of
    the time, WITHIN that true class (Mondrian/class-conditional split conformal)."""
    quantiles = {}
    for c in SEVERITY_ORDER:
        mask = y_true == c
        n_c = int(mask.sum())
        if n_c == 0:
            quantiles[c] = 0.0
            continue
        true_class_idx = classes.index(c)
        nonconformity = 1.0 - proba[mask, true_class_idx]  # higher = more surprising
        # Finite-sample-correct quantile level (standard split-conformal correction)
        level = min(1.0, np.ceil((n_c + 1) * target_coverage) / n_c)
        quantiles[c] = float(np.quantile(nonconformity, level, method="higher")) if level <= 1.0 else 1.0
    return quantiles


def build_sets(proba: np.ndarray, classes: list[str], quantiles: dict[str, float]) -> list[list[str]]:
    sets = []
    for row in proba:
        s = [c for c in SEVERITY_ORDER if row[classes.index(c)] >= 1.0 - quantiles[c]]
        if not s:  # guard: never return an empty set, fall back to the argmax class
            s = [SEVERITY_ORDER[int(np.argmax(row))]]
        sets.append(s)
    return sets


def evaluate_sets(sets: list[list[str]], y_true: np.ndarray) -> dict:
    covered = np.array([y_true[i] in sets[i] for i in range(len(y_true))])
    sizes = np.array([len(s) for s in sets])
    per_class = {}
    for c in SEVERITY_ORDER:
        mask = y_true == c
        if mask.sum() == 0:
            continue
        per_class[c] = {
            "n": int(mask.sum()),
            "coverage": round(float(covered[mask].mean()), 4),
            "avg_set_size": round(float(sizes[mask].mean()), 3),
        }
    return {
        "overall_coverage": round(float(covered.mean()), 4),
        "overall_avg_set_size": round(float(sizes.mean()), 3),
        "singleton_rate": round(float((sizes == 1).mean()), 4),
        "per_class": per_class,
    }


def main() -> None:
    print("Loading full production dataset...")
    df = load_dataset(PROCESSED_DIR / "polyguard_all_drugs_severity_pairs.csv")
    print(f"{len(df):,} rows")

    train_df, rest_df = train_test_split(df, test_size=0.30, random_state=RANDOM_STATE, stratify=df["severity"])
    cal_df, test_df = train_test_split(rest_df, test_size=0.50, random_state=RANDOM_STATE, stratify=rest_df["severity"])
    print(f"Train: {len(train_df):,} | Calibrate: {len(cal_df):,} | Test: {len(test_df):,}")

    print("Training model (identical pipeline to production Model 1) on the 70% train fold...")
    model = make_model()
    model.fit(train_df[FEATURE_COLS], train_df["severity"])
    classes = list(model.classes_)

    proba_cal = model.predict_proba(cal_df[FEATURE_COLS])
    y_cal = cal_df["severity"].to_numpy()
    proba_test = model.predict_proba(test_df[FEATURE_COLS])
    y_test = test_df["severity"].to_numpy()

    all_quantiles = {}
    all_eval = {}
    for target in TARGET_COVERAGES:
        print(f"\n=== Target coverage: {target:.0%} ===")
        quantiles = mondrian_quantiles(proba_cal, y_cal, classes, target)
        print(f"Per-class nonconformity thresholds: {quantiles}")
        all_quantiles[str(target)] = quantiles

        sets = build_sets(proba_test, classes, quantiles)
        metrics = evaluate_sets(sets, y_test)
        print(f"Held-out coverage: {metrics['overall_coverage']:.4f}  "
              f"avg set size: {metrics['overall_avg_set_size']:.3f}  "
              f"singleton rate: {metrics['singleton_rate']:.4f}")
        for c, m in metrics["per_class"].items():
            print(f"  {c:>10}: n={m['n']:>5}  coverage={m['coverage']:.3f}  avg_set_size={m['avg_set_size']:.3f}")
        all_eval[str(target)] = metrics

    # --- Also check coverage under drug-disjoint cold-start (an honest stress test -
    # conformal's guarantee assumes exchangeability with the calibration distribution,
    # which a genuinely unseen drug violates; report it rather than assume it holds). ---
    print("\n=== Cold-start stress test (20% of drugs held out entirely) ===")
    import pandas as pd
    rng = np.random.default_rng(RANDOM_STATE)
    all_drugs = pd.Index(pd.concat([df["drug_a"].str.lower().str.strip(), df["drug_b"].str.lower().str.strip()]).dropna().unique())
    cold_drugs = set(rng.choice(all_drugs, size=max(1, int(len(all_drugs) * 0.20)), replace=False))
    has_cold = df["drug_a"].str.lower().str.strip().isin(cold_drugs) | df["drug_b"].str.lower().str.strip().isin(cold_drugs)
    cold_train_df, cold_rest_df = df[~has_cold], df[has_cold]
    cold_cal_df, cold_test_df = train_test_split(cold_rest_df, test_size=0.50, random_state=RANDOM_STATE, stratify=cold_rest_df["severity"])

    cold_model = make_model()
    cold_model.fit(cold_train_df[FEATURE_COLS], cold_train_df["severity"])
    cold_classes = list(cold_model.classes_)
    cold_proba_cal = cold_model.predict_proba(cold_cal_df[FEATURE_COLS])
    cold_proba_test = cold_model.predict_proba(cold_test_df[FEATURE_COLS])

    cold_start_eval = {}
    for target in TARGET_COVERAGES:
        q = mondrian_quantiles(cold_proba_cal, cold_cal_df["severity"].to_numpy(), cold_classes, target)
        sets = build_sets(cold_proba_test, cold_classes, q)
        m = evaluate_sets(sets, cold_test_df["severity"].to_numpy())
        print(f"  target={target:.0%}  observed_coverage={m['overall_coverage']:.4f}  avg_set_size={m['overall_avg_set_size']:.3f}")
        cold_start_eval[str(target)] = m

    with open(OUT_DIR / "quantiles.json", "w", encoding="utf-8") as f:
        json.dump(all_quantiles, f, indent=2)
    with open(OUT_DIR / "eval.json", "w", encoding="utf-8") as f:
        json.dump({"standard_split": all_eval, "cold_start_split": cold_start_eval}, f, indent=2)
    print(f"\nSaved quantiles.json and eval.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
