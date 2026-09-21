from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


SEVERITY_ORDER = {"Minor": 0, "Moderate": 1, "Major": 2}
DISEASE_COLUMNS = [
    "disease_diabetes",
    "disease_ckd",
    "disease_heart_failure",
    "disease_hypertension",
]


def normalize_drug_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_pair(row: pd.Series) -> tuple[str, str]:
    left = normalize_drug_name(row["Drug_A"])
    right = normalize_drug_name(row["Drug_B"])
    return tuple(sorted((left, right)))


def most_severe(levels: pd.Series) -> str:
    return max(levels, key=lambda level: SEVERITY_ORDER[level])


def load_ddinter_all(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

    df = df.copy()
    df["Level"] = df["Level"].astype(str).str.strip()
    df = df[df["Level"].isin(SEVERITY_ORDER)].copy()
    df["drug_a_norm"] = df["Drug_A"].map(normalize_drug_name)
    df["drug_b_norm"] = df["Drug_B"].map(normalize_drug_name)
    df = df[(df["drug_a_norm"] != "") & (df["drug_b_norm"] != "")]
    df = df[df["drug_a_norm"] != df["drug_b_norm"]]

    pair_keys = df.apply(canonical_pair, axis=1, result_type="expand")
    df["pair_drug_1_norm"] = pair_keys[0]
    df["pair_drug_2_norm"] = pair_keys[1]

    grouped = (
        df.groupby(["pair_drug_1_norm", "pair_drug_2_norm"], as_index=False)
        .agg(
            drug_a=("Drug_A", "first"),
            drug_b=("Drug_B", "first"),
            ddinter_id_a=("DDInterID_A", "first"),
            ddinter_id_b=("DDInterID_B", "first"),
            severity=("Level", most_severe),
            source_rows=("Level", "size"),
        )
    )
    grouped["severity_label"] = grouped["severity"].map(SEVERITY_ORDER)

    # No disease scoping in the all-combined DDInter file: keep the same
    # feature columns as the disease-specific dataset so the existing model
    # code works unmodified, but leave every flag at 0 (context unknown).
    for column in DISEASE_COLUMNS:
        grouped[column] = 0
    grouped["diseases"] = ""

    return grouped


def add_empty_smiles_columns(pairs: pd.DataFrame) -> pd.DataFrame:
    result = pairs.copy()
    result["smiles_a"] = pd.NA
    result["smiles_b"] = pd.NA
    return result


def write_summary(df: pd.DataFrame, path: Path) -> None:
    lines = [
        "# PolyGuard all-drug severity dataset summary",
        "",
        f"Rows: {len(df)}",
        f"Unique drugs: {len(set(df['pair_drug_1_norm']).union(df['pair_drug_2_norm']))}",
        "",
        "Severity distribution:",
    ]
    for severity, count in df["severity"].value_counts().sort_index().items():
        lines.append(f"- {severity}: {count}")

    lines.extend(
        [
            "",
            "Notes:",
            "- Source: ddinter_all_combined.csv (DDInter, no disease restriction).",
            "- 'Unknown' severity rows are dropped; only Minor/Moderate/Major are kept.",
            "- Duplicate unordered drug pairs are merged; if severities conflict, the most severe label is kept.",
            "- Disease flag columns are kept for schema compatibility with the model code but are always 0 here (no disease context in this source).",
            "- SMILES coverage is left blank; filled in separately by the PubChem resolution step.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare PolyGuard all-drug (non-disease-scoped) pairwise severity data.")
    parser.add_argument("--data-dir", type=Path, default=Path(r"E:\Polypharmacy\Datasets"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"E:\Polypharmacy\processed"))
    args = parser.parse_args()

    ddinter_path = args.data_dir / "ddinter_all_combined.csv"
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs = load_ddinter_all(ddinter_path)
    pairs = add_empty_smiles_columns(pairs)

    columns = [
        "drug_a",
        "drug_b",
        "ddinter_id_a",
        "ddinter_id_b",
        "severity",
        "severity_label",
        "diseases",
        *DISEASE_COLUMNS,
        "smiles_a",
        "smiles_b",
        "source_rows",
        "pair_drug_1_norm",
        "pair_drug_2_norm",
    ]
    pairs[columns].to_csv(output_dir / "polyguard_all_drugs_severity_pairs.csv", index=False)
    write_summary(pairs, output_dir / "polyguard_all_drugs_severity_pairs_summary.md")
    print(f"Wrote {len(pairs)} rows to {output_dir / 'polyguard_all_drugs_severity_pairs.csv'}")


if __name__ == "__main__":
    main()
