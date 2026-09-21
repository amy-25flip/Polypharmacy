from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from train_eval_chemistry_model import build_dataset
from train_eval_comparison import build_pair_text

RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
C_VALUES = [0.01, 0.1, 1, 10]

PAIRS_CSV = Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv")
CACHE_PATH = Path(r"E:\Polypharmacy\processed\drug_name_smiles_cache.csv")


def main() -> None:
    kept_df, X_chem, _ = build_dataset(PAIRS_CSV, CACHE_PATH)
    y = kept_df["severity"].values
    pair_text = build_pair_text(kept_df)

    all_idx = np.arange(len(kept_df))
    all_drugs = pd.Index(
        pd.concat([kept_df["pair_drug_1_norm"], kept_df["pair_drug_2_norm"]]).dropna().unique()
    )
    rng = np.random.default_rng(RANDOM_STATE)
    cold_drugs = set(rng.choice(all_drugs, size=max(1, int(len(all_drugs) * 0.20)), replace=False))
    has_cold_drug = (
        kept_df["pair_drug_1_norm"].isin(cold_drugs) | kept_df["pair_drug_2_norm"].isin(cold_drugs)
    )
    train_idx = all_idx[(~has_cold_drug).values]
    test_idx = all_idx[has_cold_drug.values]
    y_train, y_test = y[train_idx], y[test_idx]

    vec = TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    text_train = vec.fit_transform(pair_text.iloc[train_idx])
    text_test = vec.transform(pair_text.iloc[test_idx])

    X_chem_sparse = sparse.csr_matrix(X_chem)
    chem_train, chem_test = X_chem_sparse[train_idx], X_chem_sparse[test_idx]

    hybrid_train = sparse.hstack([text_train, chem_train]).tocsr()
    hybrid_test = sparse.hstack([text_test, chem_test]).tocsr()

    print(f"{'C':>6} {'text_only macro-F1':>20} {'hybrid macro-F1':>18}  hybrid_beats_text")
    for c in C_VALUES:
        text_model = LogisticRegression(
            C=c, max_iter=1000, class_weight="balanced", solver="lbfgs", random_state=RANDOM_STATE
        )
        text_model.fit(text_train, y_train)
        text_f1 = f1_score(y_test, text_model.predict(text_test), average="macro")

        hybrid_model = LogisticRegression(
            C=c, max_iter=1000, class_weight="balanced", solver="lbfgs", random_state=RANDOM_STATE
        )
        hybrid_model.fit(hybrid_train, y_train)
        hybrid_f1 = f1_score(y_test, hybrid_model.predict(hybrid_test), average="macro")

        print(f"{c:>6} {text_f1:>20.4f} {hybrid_f1:>18.4f}  {hybrid_f1 > text_f1}")


if __name__ == "__main__":
    main()
