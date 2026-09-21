from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
DISEASE_COLS = [
    "disease_diabetes",
    "disease_ckd",
    "disease_heart_failure",
    "disease_hypertension",
]
FEATURE_COLS = ["pair_text", *DISEASE_COLS]


def load_dataset(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df.copy()
    df["severity"] = df["severity"].astype(str).str.strip()
    df = df[df["severity"].isin(SEVERITY_ORDER)].copy()

    for col in DISEASE_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(int)

    df["drug_a"] = df["drug_a"].fillna("").astype(str)
    df["drug_b"] = df["drug_b"].fillna("").astype(str)
    df["diseases"] = df.get("diseases", "").fillna("").astype(str)

    pair_parts = np.sort(df[["drug_a", "drug_b"]].values.astype(str), axis=1)
    df["pair_text"] = (
        pair_parts[:, 0]
        + " [DRUG_PAIR] "
        + pair_parts[:, 1]
        + " [DISEASE_SCOPE] "
        + df["diseases"]
    )
    df = df.drop_duplicates(subset=["pair_text", "severity"]).reset_index(drop=True)
    return df


def make_model() -> Pipeline:
    preprocess = ColumnTransformer(
        transformers=[
            (
                "pair_text",
                TfidfVectorizer(
                    lowercase=True,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                ),
                "pair_text",
            ),
            ("disease_flags", "passthrough", DISEASE_COLS),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            ("features", preprocess),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="saga",
                    n_jobs=-1,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def evaluate(model: Pipeline, data: pd.DataFrame) -> dict[str, float]:
    y_true = data["severity"]
    y_pred = model.predict(data[FEATURE_COLS])
    report = classification_report(
        y_true, y_pred, labels=SEVERITY_ORDER, output_dict=True, zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "n": len(data),
        "per_class_f1": {label: report[label]["f1-score"] for label in SEVERITY_ORDER},
    }


def run(csv_path: Path, label: str) -> dict[str, dict[str, float]]:
    df = load_dataset(csv_path)

    train_df, test_df = train_test_split(
        df, test_size=0.30, random_state=RANDOM_STATE, stratify=df["severity"]
    )
    model = make_model()
    model.fit(train_df[FEATURE_COLS], train_df["severity"])
    standard_metrics = evaluate(model, test_df)

    all_drugs = pd.Index(
        pd.concat(
            [
                df["drug_a"].str.lower().str.strip(),
                df["drug_b"].str.lower().str.strip(),
            ]
        )
        .dropna()
        .unique()
    )
    rng = np.random.default_rng(RANDOM_STATE)
    cold_drugs = set(
        rng.choice(all_drugs, size=max(1, int(len(all_drugs) * 0.20)), replace=False)
    )
    has_cold_drug = (
        df["drug_a"].str.lower().str.strip().isin(cold_drugs)
        | df["drug_b"].str.lower().str.strip().isin(cold_drugs)
    )
    cold_train_df = df[~has_cold_drug].copy()
    cold_test_df = df[has_cold_drug].copy()

    cold_model = make_model()
    cold_model.fit(cold_train_df[FEATURE_COLS], cold_train_df["severity"])
    cold_metrics = evaluate(cold_model, cold_test_df)

    # Majority-class baseline, for context on how much the real model earns.
    majority_class = train_df["severity"].value_counts().idxmax()
    majority_pred = pd.Series([majority_class] * len(test_df))
    majority_metrics = {
        "accuracy": accuracy_score(test_df["severity"], majority_pred),
        "macro_f1": f1_score(test_df["severity"], majority_pred, average="macro"),
        "n": len(test_df),
    }

    print(f"\n=== {label} ===")
    print(f"Dataset: {len(df)} rows, "
          f"{len(set(df['drug_a'].str.lower()).union(df['drug_b'].str.lower()))} unique drugs")
    print(f"Severity distribution: {df['severity'].value_counts().to_dict()}")
    print(f"Majority-class baseline   -> accuracy {majority_metrics['accuracy']:.4f}  macro-F1 {majority_metrics['macro_f1']:.4f}")
    print(f"Standard test ({standard_metrics['n']} rows) -> accuracy {standard_metrics['accuracy']:.4f}  macro-F1 {standard_metrics['macro_f1']:.4f}  per-class F1 {standard_metrics['per_class_f1']}")
    print(f"Cold-start test ({cold_metrics['n']} rows)  -> accuracy {cold_metrics['accuracy']:.4f}  macro-F1 {cold_metrics['macro_f1']:.4f}  per-class F1 {cold_metrics['per_class_f1']}")

    return {"majority": majority_metrics, "standard": standard_metrics, "cold_start": cold_metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/evaluate the PolyGuard severity baseline on a given CSV.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    run(args.csv_path, args.label or args.csv_path.name)


if __name__ == "__main__":
    main()
