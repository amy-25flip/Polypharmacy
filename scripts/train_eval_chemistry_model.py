from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RDLogger.DisableLog("rdApp.*")

RANDOM_STATE = 42
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
N_BITS = 1024
RADIUS = 2

_generator = rdFingerprintGenerator.GetMorganGenerator(radius=RADIUS, fpSize=N_BITS)


def smiles_to_bits(smiles: str) -> np.ndarray | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = _generator.GetFingerprint(mol)
    arr = np.zeros((N_BITS,), dtype=np.float32)
    for bit in fp.GetOnBits():
        arr[bit] = 1.0
    return arr


def load_fingerprint_lookup(cache_path: Path) -> dict[str, np.ndarray]:
    df = pd.read_csv(cache_path)
    lookup: dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        smiles = row.get("smiles")
        if pd.isna(smiles) or not str(smiles).strip():
            continue
        bits = smiles_to_bits(str(smiles))
        if bits is not None:
            lookup[row["drug_name_norm"]] = bits
    return lookup


def build_dataset(pairs_csv: Path, cache_path: Path) -> tuple[pd.DataFrame, np.ndarray, int]:
    df = pd.read_csv(pairs_csv)
    df["severity"] = df["severity"].astype(str).str.strip()
    df = df[df["severity"].isin(SEVERITY_ORDER)].copy()
    total_pairs = len(df)

    fingerprints = load_fingerprint_lookup(cache_path)
    names = list(fingerprints.keys())
    name_to_idx = {name: i for i, name in enumerate(names)}
    fp_matrix = np.vstack([fingerprints[name] for name in names]) if names else np.empty((0, N_BITS))

    idx_a = df["pair_drug_1_norm"].astype(str).map(name_to_idx)
    idx_b = df["pair_drug_2_norm"].astype(str).map(name_to_idx)
    mask = idx_a.notna() & idx_b.notna()

    kept_df = df[mask].reset_index(drop=True)
    idx_a_arr = idx_a[mask].astype(int).to_numpy()
    idx_b_arr = idx_b[mask].astype(int).to_numpy()

    fp_a = fp_matrix[idx_a_arr]
    fp_b = fp_matrix[idx_b_arr]

    abs_diff = np.abs(fp_a - fp_b)
    elementwise_and = np.minimum(fp_a, fp_b)
    elementwise_or = np.maximum(fp_a, fp_b)
    elementwise_product = fp_a * fp_b
    intersection = elementwise_and.sum(axis=1)
    union = elementwise_or.sum(axis=1)
    tanimoto = np.divide(
        intersection, union, out=np.zeros_like(intersection), where=union > 0
    ).reshape(-1, 1)

    feature_matrix = np.hstack(
        [abs_diff, elementwise_and, elementwise_or, elementwise_product, tanimoto]
    ).astype(np.float32)

    return kept_df, feature_matrix, total_pairs


def evaluate(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    report = classification_report(
        y_true, y_pred, labels=SEVERITY_ORDER, output_dict=True, zero_division=0
    )
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "n": len(y_true),
        "per_class_f1": {label: report[label]["f1-score"] for label in SEVERITY_ORDER},
    }


def make_model() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler(with_mean=False)),
            (
                "classifier",
                LogisticRegression(
                    max_iter=500,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/evaluate a chemistry (Morgan fingerprint) DDI severity model.")
    parser.add_argument(
        "--pairs-csv",
        type=Path,
        default=Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv"),
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path(r"E:\Polypharmacy\processed\drug_name_smiles_cache.csv"),
    )
    args = parser.parse_args()

    kept_df, X, total_pairs = build_dataset(args.pairs_csv, args.cache_path)
    coverage = len(kept_df) / total_pairs if total_pairs else 0.0

    print(f"Coverage: {len(kept_df)}/{total_pairs} pairs have both drugs resolved to a valid structure "
          f"({coverage:.1%}).")
    if len(kept_df) < 200:
        print("Too few resolved pairs to train a meaningful model yet.")
        return

    y = kept_df["severity"].values

    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, kept_df.index.values, test_size=0.30, random_state=RANDOM_STATE, stratify=y
    )
    model = make_model()
    model.fit(X_train, y_train)
    standard_metrics = evaluate(pd.Series(y_test), model.predict(X_test))

    all_drugs = pd.Index(
        pd.concat(
            [kept_df["pair_drug_1_norm"], kept_df["pair_drug_2_norm"]]
        ).dropna().unique()
    )
    rng = np.random.default_rng(RANDOM_STATE)
    cold_drugs = set(rng.choice(all_drugs, size=max(1, int(len(all_drugs) * 0.20)), replace=False))
    has_cold_drug = (
        kept_df["pair_drug_1_norm"].isin(cold_drugs) | kept_df["pair_drug_2_norm"].isin(cold_drugs)
    )
    cold_train_mask = (~has_cold_drug).values
    cold_test_mask = has_cold_drug.values

    cold_model = make_model()
    cold_model.fit(X[cold_train_mask], y[cold_train_mask])
    cold_metrics = evaluate(pd.Series(y[cold_test_mask]), cold_model.predict(X[cold_test_mask]))

    majority_class = pd.Series(y_train).value_counts().idxmax()
    majority_pred = np.array([majority_class] * len(y_test))
    majority_metrics = evaluate(pd.Series(y_test), majority_pred)

    print("\n=== Chemistry model (Morgan fingerprints, pair ops: abs-diff / AND / OR / product / Tanimoto) ===")
    print(f"Majority-class baseline   -> accuracy {majority_metrics['accuracy']:.4f}  macro-F1 {majority_metrics['macro_f1']:.4f}")
    print(f"Standard test ({standard_metrics['n']} rows) -> accuracy {standard_metrics['accuracy']:.4f}  macro-F1 {standard_metrics['macro_f1']:.4f}  per-class F1 {standard_metrics['per_class_f1']}")
    print(f"Cold-start test ({cold_metrics['n']} rows)  -> accuracy {cold_metrics['accuracy']:.4f}  macro-F1 {cold_metrics['macro_f1']:.4f}  per-class F1 {cold_metrics['per_class_f1']}")


if __name__ == "__main__":
    main()
