from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

HETIONET_NODES = Path(r"E:\Polypharmacy\Datasets\hetionet-v1.0-nodes.tsv")
SMILES_PATH = Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv")
OUTPUT_PATH = Path(r"E:\Polypharmacy\processed\drug_name_to_drugbank_id.json")


def normalize(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    return re.sub(r"\s+", " ", text.strip().lower())


def main() -> None:
    het = pd.read_csv(HETIONET_NODES, sep="\t")
    compounds = het[het["kind"] == "Compound"].copy()
    compounds["norm_name"] = compounds["name"].map(normalize)
    compounds["drugbank_id"] = compounds["id"].str.replace("Compound::", "", regex=False)

    smiles_df = pd.read_csv(SMILES_PATH)
    has_smiles = set(
        smiles_df.loc[smiles_df["smiles"].notna() & (smiles_df["smiles"].astype(str).str.strip() != ""), "drugbank_id"]
    )

    lookup = {
        row["norm_name"]: row["drugbank_id"]
        for _, row in compounds.iterrows()
        if row["drugbank_id"] in has_smiles
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(lookup, f, indent=2)
    print(f"Wrote {len(lookup)} drug-name -> DrugBankID mappings (only IDs with a usable SMILES) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
