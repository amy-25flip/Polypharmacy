from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import pandas as pd

FILES = ["3_drug.csv", "3_drugnegative.csv", "4_drug.csv", "4_drugnegative.csv", "5_drug.csv", "5_drugnegative.csv"]

CATEGORICAL_COLS = [
    "condition",
    "country",
    "gender",
    "quarter",
    "reporter_category",
    "reporter_description",
    "reporter_qualify_code",
]


def parse_drug_list(value: str) -> list[str]:
    return ast.literal_eval(value)


def load_all(data_dir: Path) -> pd.DataFrame:
    frames = []
    for fname in FILES:
        df = pd.read_csv(data_dir / fname)
        df["source_file"] = fname
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)

    combined["drug_ids"] = combined["DrugBankID"].map(parse_drug_list)
    combined["set_size"] = combined["drug_ids"].map(len)
    combined["base_report_id"] = combined["report_id"].astype(str).str.rstrip("n")
    combined["label"] = (combined["hyperedge_label"] == 1).astype(int)
    return combined


def load_smiles_lookup(smiles_path: Path) -> dict[str, str]:
    df = pd.read_csv(smiles_path)
    return {
        row["drugbank_id"]: str(row["smiles"]).strip()
        for _, row in df.iterrows()
        if pd.notna(row["smiles"]) and str(row["smiles"]).strip()
    }


def build_vocab(series: pd.Series) -> dict[str, int]:
    values = sorted(series.astype(str).unique())
    return {value: idx + 1 for idx, value in enumerate(values)}  # 0 reserved for unknown/pad


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the combined HODDI higher-order dataset for the DeepSets model.")
    parser.add_argument("--data-dir", type=Path, default=Path(r"E:\Polypharmacy\Datasets"))
    parser.add_argument("--smiles-path", type=Path, default=Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"E:\Polypharmacy\processed"))
    args = parser.parse_args()

    combined = load_all(args.data_dir)
    print(f"Loaded {len(combined)} rows across {len(FILES)} files "
          f"({combined['set_size'].value_counts().to_dict()} by set size).")
    print(f"Label balance: {combined['label'].value_counts().to_dict()}")

    smiles_lookup = load_smiles_lookup(args.smiles_path)
    print(f"{len(smiles_lookup)} DrugBank IDs have a usable SMILES locally.")

    def all_drugs_resolved(drug_ids: list[str]) -> bool:
        return all(d in smiles_lookup for d in drug_ids)

    combined["all_resolved"] = combined["drug_ids"].map(all_drugs_resolved)
    coverage = combined["all_resolved"].mean()
    print(f"Rows with every drug in the set resolved to a structure: "
          f"{combined['all_resolved'].sum()}/{len(combined)} ({coverage:.1%}).")

    kept = combined[combined["all_resolved"]].copy().reset_index(drop=True)
    print(f"Label balance after filtering to resolved sets: {kept['label'].value_counts().to_dict()}")

    # Build vocabs (fit on the KEPT/usable rows only, so index space matches what training will see).
    vocabs: dict[str, dict[str, int]] = {}
    for col in CATEGORICAL_COLS:
        vocabs[col] = build_vocab(kept[col])
    vocabs["SE_above_0.9"] = build_vocab(kept["SE_above_0.9"])

    args.output_dir.mkdir(parents=True, exist_ok=True)

    out_cols = [
        "report_id", "base_report_id", "source_file", "set_size", "label",
        "drug_ids", "SE_above_0.9", "age",
        *CATEGORICAL_COLS,
    ]
    kept_out = kept[out_cols].copy()
    kept_out["drug_ids"] = kept_out["drug_ids"].map(lambda ids: "|".join(ids))
    kept_out.to_csv(args.output_dir / "hoddi_prepared.csv", index=False)

    with open(args.output_dir / "hoddi_vocabs.json", "w", encoding="utf-8") as f:
        json.dump(vocabs, f, indent=2)

    print(f"Wrote {len(kept_out)} rows to {args.output_dir / 'hoddi_prepared.csv'}")
    print(f"Wrote vocabs to {args.output_dir / 'hoddi_vocabs.json'} "
          f"({', '.join(f'{k}: {len(v)}' for k, v in vocabs.items())})")


if __name__ == "__main__":
    main()
