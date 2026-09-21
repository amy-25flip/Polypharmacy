import itertools

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
SEVERITY_RANK = {"Minor": 0, "Moderate": 1, "Major": 2}
CSV_PATH = r"E:\Polypharmacy\processed\polyguard_severity_pairs.csv"


df = pd.read_csv(CSV_PATH)
df = df.copy()
df["severity"] = df["severity"].astype(str).str.strip()
df = df[df["severity"].isin(SEVERITY_ORDER)].copy()

disease_cols = [
    "disease_diabetes",
    "disease_ckd",
    "disease_heart_failure",
    "disease_hypertension",
]

for col in disease_cols:
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

train_df, _ = train_test_split(
    df,
    test_size=0.30,
    random_state=RANDOM_STATE,
    stratify=df["severity"],
)

feature_cols = ["pair_text", *disease_cols]


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
            ("disease_flags", "passthrough", disease_cols),
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


model = make_model()
model.fit(train_df[feature_cols], train_df["severity"])


def predict_pair(drug_a: str, drug_b: str, diseases: str = "") -> dict[str, object]:
    row = pd.DataFrame(
        [
            {
                "pair_text": " [DRUG_PAIR] ".join(sorted([drug_a, drug_b]))
                + " [DISEASE_SCOPE] "
                + diseases,
                "disease_diabetes": int("diabetes" in diseases.lower()),
                "disease_ckd": int("kidney" in diseases.lower() or "ckd" in diseases.lower()),
                "disease_heart_failure": int("heart" in diseases.lower()),
                "disease_hypertension": int("hypertension" in diseases.lower()),
            }
        ]
    )

    predicted_severity = model.predict(row[feature_cols])[0]
    probabilities = model.predict_proba(row[feature_cols])[0]
    classes = list(model.named_steps["classifier"].classes_)

    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "predicted_severity": predicted_severity,
        "confidence": float(np.max(probabilities)),
        **{
            f"prob_{severity_class}": float(probabilities[index])
            for index, severity_class in enumerate(classes)
        },
    }


def predict_regimen(drugs: list[str], diseases: str = "") -> tuple[str, pd.DataFrame]:
    pair_results = [
        predict_pair(drug_a, drug_b, diseases)
        for drug_a, drug_b in itertools.combinations(drugs, 2)
    ]
    results = pd.DataFrame(pair_results)
    if results.empty:
        return "No pair to score", results

    results["severity_rank"] = results["predicted_severity"].map(SEVERITY_RANK)
    highest_risk_row = results.sort_values(
        ["severity_rank", "confidence"],
        ascending=False,
    ).iloc[0]
    return highest_risk_row["predicted_severity"], results.drop(columns=["severity_rank"])


overall_severity, pair_table = predict_regimen(
    ["Metformin", "Warfarin", "Furosemide", "Lisinopril"],
    diseases="Diabetes|Hypertension|Heart Failure",
)

print("Overall regimen severity:", overall_severity)
print(pair_table.sort_values(["predicted_severity", "confidence"], ascending=False).to_string(index=False))
