"""
Model 4 (research branch) - Step 3: build the training dataset.

Restricts polyguard_all_drugs_severity_pairs.csv to pairs where BOTH drugs
have a resolved SMILES string (for the GATv2 molecular encoder) AND a node
in the Hetionet KG-embedding subgraph (for the KG feature). This is a real
constraint of the graph/chemistry approach - Model 1 (production) doesn't
need it because it only looks at drug name text, which is why Model 1 covers
all 1,902 drugs and Model 4 will only cover ~980.

Produces the SAME two evaluation protocols already used for Model 1
(scripts/train_eval_severity_model.py), so results are directly comparable:
  - "standard" split: 70/30 stratified by severity, random_state=42
  - "cold_start" split: 20% of drugs held out entirely from training
Both splits, and the full usable dataset, are saved to processed/model4/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "model4"
RANDOM_STATE = 42


def normalize(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "polyguard_all_drugs_severity_pairs.csv")
    df = df[df["severity"].isin(["Minor", "Moderate", "Major"])].copy()

    smiles_cache = pd.read_csv(PROCESSED_DIR / "drug_name_smiles_cache.csv")
    name_to_smiles = {
        row.drug_name_norm: row.smiles
        for row in smiles_cache.itertuples()
        if isinstance(row.smiles, str) and len(row.smiles) > 0
    }

    name_to_id = json.load(open(PROCESSED_DIR / "drug_name_to_drugbank_id.json", encoding="utf-8"))
    kg_idx = json.load(open(OUT_DIR / "kg_entity_to_idx.json", encoding="utf-8"))
    kg_compound_ids = {k.split("::")[1] for k in kg_idx if k.startswith("Compound::")}

    def usable(name: str) -> bool:
        n = normalize(name)
        if n not in name_to_smiles:
            return False
        did = name_to_id.get(n)
        return bool(did) and did in kg_compound_ids

    mask = df["drug_a"].apply(usable) & df["drug_b"].apply(usable)
    usable_df = df[mask].reset_index(drop=True)
    print(f"Usable pairs (SMILES + KG coverage on both drugs): {len(usable_df):,} / {len(df):,}")
    print(usable_df["severity"].value_counts())

    unique_drugs = sorted(set(usable_df["drug_a"]) | set(usable_df["drug_b"]))
    drug_to_node_idx = {d: i for i, d in enumerate(unique_drugs)}
    print(f"Unique drugs in Model 4 dataset: {len(unique_drugs)}")

    node_table = pd.DataFrame({
        "drug_name": unique_drugs,
        "node_idx": [drug_to_node_idx[d] for d in unique_drugs],
        "drugbank_id": [name_to_id[normalize(d)] for d in unique_drugs],
        "smiles": [name_to_smiles[normalize(d)] for d in unique_drugs],
    })
    node_table.to_csv(OUT_DIR / "model4_nodes.csv", index=False)

    usable_df["node_a"] = usable_df["drug_a"].map(drug_to_node_idx)
    usable_df["node_b"] = usable_df["drug_b"].map(drug_to_node_idx)
    usable_df = usable_df[["drug_a", "drug_b", "node_a", "node_b", "severity"]]
    usable_df.to_csv(OUT_DIR / "model4_pairs.csv", index=False)

    # --- Standard split: 70/30 stratified by severity ---
    train_std, test_std = train_test_split(
        usable_df, test_size=0.30, random_state=RANDOM_STATE, stratify=usable_df["severity"]
    )
    train_std.to_csv(OUT_DIR / "model4_train_standard.csv", index=False)
    test_std.to_csv(OUT_DIR / "model4_test_standard.csv", index=False)
    print(f"Standard split: {len(train_std)} train / {len(test_std)} test")

    # --- Cold-start split: 20% of drugs held out entirely from training ---
    rng = np.random.default_rng(RANDOM_STATE)
    cold_drugs = set(rng.choice(unique_drugs, size=max(1, int(len(unique_drugs) * 0.20)), replace=False))
    has_cold_drug = usable_df["drug_a"].isin(cold_drugs) | usable_df["drug_b"].isin(cold_drugs)
    train_cold = usable_df[~has_cold_drug].copy()
    test_cold = usable_df[has_cold_drug].copy()
    train_cold.to_csv(OUT_DIR / "model4_train_coldstart.csv", index=False)
    test_cold.to_csv(OUT_DIR / "model4_test_coldstart.csv", index=False)
    print(f"Cold-start split: {len(train_cold)} train / {len(test_cold)} test ({len(cold_drugs)} held-out drugs)")

    with open(OUT_DIR / "model4_dataset_summary.md", "w", encoding="utf-8") as f:
        f.write("# Model 4 dataset summary\n\n")
        f.write(f"- Usable pairs: {len(usable_df):,} / {len(df):,} full production dataset\n")
        f.write(f"- Unique drugs: {len(unique_drugs)} (vs. 1,902 in Model 1's full vocabulary)\n")
        f.write(f"- Severity distribution: {usable_df['severity'].value_counts().to_dict()}\n")
        f.write(f"- Standard split: {len(train_std)} train / {len(test_std)} test (70/30, stratified, seed 42)\n")
        f.write(f"- Cold-start split: {len(train_cold)} train / {len(test_cold)} test "
                f"({len(cold_drugs)} drugs held out entirely, seed 42)\n")


if __name__ == "__main__":
    main()
