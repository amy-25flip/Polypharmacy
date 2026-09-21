from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


def normalize_drug_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def load_unique_drug_names(pairs_csv: Path) -> dict[str, str]:
    df = pd.read_csv(pairs_csv)
    names_a = df["drug_a"].dropna().map(str)
    names_b = df["drug_b"].dropna().map(str)
    seen: dict[str, str] = {}
    for name in pd.concat([names_a, names_b]):
        norm = normalize_drug_name(name)
        if norm and norm not in seen:
            seen[norm] = name.strip()
    return seen


def build_hetionet_drugbank_lookup(hetionet_nodes_path: Path, smiles_path: Path) -> dict[str, str]:
    het = pd.read_csv(hetionet_nodes_path, sep="\t")
    compounds = het[het["kind"] == "Compound"].copy()
    compounds["norm_name"] = compounds["name"].map(normalize_drug_name)
    compounds["drugbank_id"] = compounds["id"].str.replace("Compound::", "", regex=False)

    smiles_df = pd.read_csv(smiles_path)
    smiles_lookup = dict(zip(smiles_df["drugbank_id"], smiles_df["smiles"]))

    name_to_smiles: dict[str, str] = {}
    for _, row in compounds.iterrows():
        smi = smiles_lookup.get(row["drugbank_id"])
        if pd.notna(smi) and str(smi).strip():
            name_to_smiles[row["norm_name"]] = str(smi).strip()
    return name_to_smiles


def load_existing_cache_names(cache_path: Path) -> set[str]:
    if not cache_path.exists():
        return set()
    df = pd.read_csv(cache_path)
    return {
        row["drug_name_norm"]
        for _, row in df.iterrows()
        if pd.notna(row.get("smiles")) and str(row.get("smiles")).strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve drug names to SMILES using local Hetionet + DrugBank data only (no API).")
    parser.add_argument("--pairs-csv", type=Path, default=Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv"))
    parser.add_argument("--hetionet-nodes", type=Path, default=Path(r"E:\Polypharmacy\Datasets\hetionet-v1.0-nodes.tsv"))
    parser.add_argument("--drugbank-smiles", type=Path, default=Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv"))
    parser.add_argument("--cache-path", type=Path, default=Path(r"E:\Polypharmacy\processed\drug_name_smiles_cache.csv"))
    args = parser.parse_args()

    unique_names = load_unique_drug_names(args.pairs_csv)
    print(f"{len(unique_names)} unique drug names in dataset.")

    het_lookup = build_hetionet_drugbank_lookup(args.hetionet_nodes, args.drugbank_smiles)
    print(f"{len(het_lookup)} Hetionet compounds have a usable local SMILES.")

    already_cached = load_existing_cache_names(args.cache_path)

    new_rows = []
    resolved = 0
    for norm_name, original_name in unique_names.items():
        if norm_name in already_cached:
            continue
        smiles = het_lookup.get(norm_name, "")
        if smiles:
            resolved += 1
        new_rows.append({"drug_name_norm": norm_name, "drug_name_original": original_name, "smiles": smiles})

    new_df = pd.DataFrame(new_rows)
    if args.cache_path.exists():
        new_df.to_csv(args.cache_path, mode="a", header=False, index=False)
    else:
        new_df.to_csv(args.cache_path, index=False)

    total_resolved = resolved + len(already_cached)
    print(f"Resolved {resolved} new names locally this run "
          f"({total_resolved}/{len(unique_names)} = {total_resolved/len(unique_names):.1%} total coverage).")
    print(f"Cache written to {args.cache_path}")


if __name__ == "__main__":
    main()
