from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

from train_eval_chemistry_model import build_dataset

RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]


def build_pair_text(df: pd.DataFrame) -> pd.Series:
    pair_parts = np.sort(df[["drug_a", "drug_b"]].values.astype(str), axis=1)
    diseases = df.get("diseases", "").fillna("").astype(str)
    return pd.Series(
        pair_parts[:, 0] + " [DRUG_PAIR] " + pair_parts[:, 1] + " [DISEASE_SCOPE] " + diseases,
        index=df.index,
    )


def evaluate(y_true, y_pred) -> dict:
    report = classification_report(
        y_true, y_pred, labels=SEVERITY_ORDER, output_dict=True, zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "n": len(y_true),
        "per_class_f1": {label: round(report[label]["f1-score"], 3) for label in SEVERITY_ORDER},
    }


def fit_predict(X_train, y_train, X_test, max_iter: int = 1000) -> np.ndarray:
    model = LogisticRegression(
        max_iter=max_iter,
        class_weight="balanced",
        solver="lbfgs",
        random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)
    return model.predict(X_test)


def print_distribution(name: str, y) -> None:
    counts = pd.Series(y).value_counts().to_dict()
    print(f"  {name}: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fair text-only vs chemistry-only vs hybrid comparison on the resolved subset.")
    parser.add_argument("--pairs-csv", type=Path, default=Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv"))
    parser.add_argument("--cache-path", type=Path, default=Path(r"E:\Polypharmacy\processed\drug_name_smiles_cache.csv"))
    args = parser.parse_args()

    full_df = pd.read_csv(args.pairs_csv)
    full_df["severity"] = full_df["severity"].astype(str).str.strip()
    full_df = full_df[full_df["severity"].isin(SEVERITY_ORDER)]

    kept_df, X_chem, total_pairs = build_dataset(args.pairs_csv, args.cache_path)
    y = kept_df["severity"].values

    print("Class distribution:")
    print_distribution("Full dataset", full_df["severity"])
    print_distribution("Resolved subset", kept_df["severity"])

    pair_text = build_pair_text(kept_df)

    # Identical standard split across all three models.
    all_idx = np.arange(len(kept_df))
    idx_train, idx_test, y_train, y_test = train_test_split(
        all_idx, y, test_size=0.30, random_state=RANDOM_STATE, stratify=y
    )
    print_distribution("Standard train", y_train)
    print_distribution("Standard test", y_test)

    # Identical cold-start split across all three models.
    all_drugs = pd.Index(
        pd.concat([kept_df["pair_drug_1_norm"], kept_df["pair_drug_2_norm"]]).dropna().unique()
    )
    rng = np.random.default_rng(RANDOM_STATE)
    cold_drugs = set(rng.choice(all_drugs, size=max(1, int(len(all_drugs) * 0.20)), replace=False))
    has_cold_drug = (
        kept_df["pair_drug_1_norm"].isin(cold_drugs) | kept_df["pair_drug_2_norm"].isin(cold_drugs)
    )
    cold_train_idx = all_idx[(~has_cold_drug).values]
    cold_test_idx = all_idx[has_cold_drug.values]
    print_distribution("Cold-start train", y[cold_train_idx])
    print_distribution("Cold-start test", y[cold_test_idx])

    # --- Text features (TF-IDF fit on train rows only, per split, to avoid leakage) ---
    def text_features(train_idx, test_idx):
        vec = TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), min_df=2)
        X_train = vec.fit_transform(pair_text.iloc[train_idx])
        X_test = vec.transform(pair_text.iloc[test_idx])
        return X_train, X_test

    X_chem_sparse = sparse.csr_matrix(X_chem)

    results = {}

    for split_name, train_idx, test_idx in [
        ("standard", idx_train, idx_test),
        ("cold_start", cold_train_idx, cold_test_idx),
    ]:
        y_tr, y_te = y[train_idx], y[test_idx]

        text_train, text_test = text_features(train_idx, test_idx)
        pred_text = fit_predict(text_train, y_tr, text_test)
        results[("text_only", split_name)] = evaluate(y_te, pred_text)

        chem_train, chem_test = X_chem_sparse[train_idx], X_chem_sparse[test_idx]
        pred_chem = fit_predict(chem_train, y_tr, chem_test)
        results[("chem_only", split_name)] = evaluate(y_te, pred_chem)

        hybrid_train = sparse.hstack([text_train, chem_train]).tocsr()
        hybrid_test = sparse.hstack([text_test, chem_test]).tocsr()
        pred_hybrid = fit_predict(hybrid_train, y_tr, hybrid_test)
        results[("hybrid", split_name)] = evaluate(y_te, pred_hybrid)

        majority_class = pd.Series(y_tr).value_counts().idxmax()
        pred_majority = np.array([majority_class] * len(y_te))
        results[("majority", split_name)] = evaluate(y_te, pred_majority)

    coverage = len(kept_df) / total_pairs if total_pairs else 0.0
    print(f"\n=== Fair comparison on resolved subset ({len(kept_df)}/{total_pairs} pairs, {coverage:.1%}) ===")
    print(f"{'Model':<12} {'Split':<12} {'Accuracy':>9} {'Macro-F1':>9}  Per-class F1")
    for model_name in ["majority", "text_only", "chem_only", "hybrid"]:
        for split_name in ["standard", "cold_start"]:
            m = results[(model_name, split_name)]
            print(f"{model_name:<12} {split_name:<12} {m['accuracy']:>9.4f} {m['macro_f1']:>9.4f}  {m['per_class_f1']}")


if __name__ == "__main__":
    main()
