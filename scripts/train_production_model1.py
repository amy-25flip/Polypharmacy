from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
DISEASE_COLS = ["disease_diabetes", "disease_ckd", "disease_heart_failure", "disease_hypertension"]
FEATURE_COLS = ["pair_text", *DISEASE_COLS]

PAIRS_CSV = Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv")
OUTPUT_DIR = Path(r"E:\Polypharmacy\processed")


def load_dataset(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
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
        pair_parts[:, 0] + " [DRUG_PAIR] " + pair_parts[:, 1] + " [DISEASE_SCOPE] " + df["diseases"]
    )
    df = df.drop_duplicates(subset=["pair_text", "severity"]).reset_index(drop=True)
    return df


def make_model() -> Pipeline:
    preprocess = ColumnTransformer(
        transformers=[
            ("pair_text", TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), min_df=2), "pair_text"),
            ("disease_flags", "passthrough", DISEASE_COLS),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            ("features", preprocess),
            ("classifier", LogisticRegression(
                max_iter=2000, class_weight="balanced", solver="saga", random_state=RANDOM_STATE,
            )),
        ]
    )


def main() -> None:
    df = load_dataset(PAIRS_CSV)
    print(f"Training production Model 1 on all {len(df)} rows (no held-out split - this is the deployed model).")

    model = make_model()
    model.fit(df[FEATURE_COLS], df["severity"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, OUTPUT_DIR / "model1_severity_pipeline.joblib")
    print(f"Saved model to {OUTPUT_DIR / 'model1_severity_pipeline.joblib'}")

    drug_names = sorted(set(df["drug_a"]) | set(df["drug_b"]))
    with open(OUTPUT_DIR / "drug_vocabulary.json", "w", encoding="utf-8") as f:
        json.dump(drug_names, f, indent=2)
    print(f"Saved {len(drug_names)} drug names to {OUTPUT_DIR / 'drug_vocabulary.json'}")


if __name__ == "__main__":
    main()
