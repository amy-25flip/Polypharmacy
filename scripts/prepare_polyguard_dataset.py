from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


SEVERITY_ORDER = {"Minor": 0, "Moderate": 1, "Major": 2}
DISEASE_COLUMNS = {
    "Diabetes": "disease_diabetes",
    "Kidney Disease": "disease_ckd",
    "Heart Failure": "disease_heart_failure",
    "Hypertension": "disease_hypertension",
}


def normalize_drug_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def canonical_pair(row: pd.Series) -> tuple[str, str]:
    left = normalize_drug_name(row["Drug_A"])
    right = normalize_drug_name(row["Drug_B"])
    return tuple(sorted((left, right)))


def split_diseases(value: object) -> set[str]:
    if pd.isna(value):
        return set()
    return {item.strip() for item in str(value).split("|") if item.strip()}


def most_severe(levels: pd.Series) -> str:
    return max(levels, key=lambda level: SEVERITY_ORDER[level])


def load_ddinter_scoped(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level", "Diseases"}
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

    for disease_name, column in DISEASE_COLUMNS.items():
        df[column] = df["Diseases"].map(lambda value: int(disease_name in split_diseases(value)))

    grouped = (
        df.groupby(["pair_drug_1_norm", "pair_drug_2_norm"], as_index=False)
        .agg(
            drug_a=("Drug_A", "first"),
            drug_b=("Drug_B", "first"),
            ddinter_id_a=("DDInterID_A", "first"),
            ddinter_id_b=("DDInterID_B", "first"),
            severity=("Level", most_severe),
            diseases=("Diseases", lambda values: "|".join(sorted(set("|".join(values).split("|"))))),
            disease_diabetes=("disease_diabetes", "max"),
            disease_ckd=("disease_ckd", "max"),
            disease_heart_failure=("disease_heart_failure", "max"),
            disease_hypertension=("disease_hypertension", "max"),
            source_rows=("Level", "size"),
        )
    )
    grouped["severity_label"] = grouped["severity"].map(SEVERITY_ORDER)
    return grouped


def load_formulary(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Formulary file not found: {path}")

    df = pd.read_csv(path)
    drug_column = next((column for column in df.columns if column.lower() in {"drug", "drug_name", "name"}), None)
    if drug_column is None:
        drug_column = df.columns[0]
    drugs = {normalize_drug_name(value) for value in df[drug_column].dropna()}
    return {drug for drug in drugs if drug}


def filter_to_formulary(pairs: pd.DataFrame, formulary: set[str] | None) -> pd.DataFrame:
    if formulary is None:
        return pairs
    mask = pairs["pair_drug_1_norm"].isin(formulary) & pairs["pair_drug_2_norm"].isin(formulary)
    return pairs[mask].copy()


def build_candidate_formulary(pairs: pd.DataFrame) -> pd.DataFrame:
    records = []
    for side in ["drug_a", "drug_b"]:
        disease_cols = list(DISEASE_COLUMNS.values())
        side_df = pairs[[side, *disease_cols]].rename(columns={side: "drug"})
        records.append(side_df)

    drugs = pd.concat(records, ignore_index=True)
    drugs["drug_norm"] = drugs["drug"].map(normalize_drug_name)
    grouped = (
        drugs.groupby("drug_norm", as_index=False)
        .agg(
            drug=("drug", "first"),
            interaction_rows=("drug", "size"),
            disease_diabetes=("disease_diabetes", "max"),
            disease_ckd=("disease_ckd", "max"),
            disease_heart_failure=("disease_heart_failure", "max"),
            disease_hypertension=("disease_hypertension", "max"),
        )
        .sort_values(["interaction_rows", "drug"], ascending=[False, True])
    )
    return grouped


def add_empty_smiles_columns(pairs: pd.DataFrame) -> pd.DataFrame:
    result = pairs.copy()
    result["smiles_a"] = pd.NA
    result["smiles_b"] = pd.NA
    return result


def write_summary(df: pd.DataFrame, path: Path) -> None:
    lines = [
        "# PolyGuard cleaned severity dataset summary",
        "",
        f"Rows: {len(df)}",
        f"Unique drugs: {len(set(df['pair_drug_1_norm']).union(df['pair_drug_2_norm']))}",
        "",
        "Severity distribution:",
    ]
    for severity, count in df["severity"].value_counts().sort_index().items():
        lines.append(f"- {severity}: {count}")

    lines.extend(["", "Disease coverage:"])
    for column in DISEASE_COLUMNS.values():
        lines.append(f"- {column}: {int(df[column].sum())}")

    lines.extend(
        [
            "",
            "Notes:",
            "- Severity is taken from DDInter's scoped four-disease file.",
            "- Duplicate unordered drug pairs are merged; if severities conflict, the most severe label is kept.",
            "- SMILES coverage is left blank unless a reliable name/ID mapping is added; the available DDInter IDs do not directly match DrugBank IDs.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare PolyGuard scoped pairwise severity data.")
    parser.add_argument("--data-dir", type=Path, default=Path(r"E:\Polypharmacy\Datasets"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"E:\Polypharmacy\processed"))
    parser.add_argument(
        "--formulary",
        type=Path,
        default=None,
        help="Optional CSV containing approved in-scope medicines. Uses a column named drug/drug_name/name, or the first column.",
    )
    args = parser.parse_args()

    ddinter_path = args.data_dir / "ddinter_4diseases_filtered.csv"
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    pairs = load_ddinter_scoped(ddinter_path)
    build_candidate_formulary(pairs).to_csv(output_dir / "candidate_formulary_drugs.csv", index=False)
    pairs = filter_to_formulary(pairs, load_formulary(args.formulary))
    pairs = add_empty_smiles_columns(pairs)

    columns = [
        "drug_a",
        "drug_b",
        "ddinter_id_a",
        "ddinter_id_b",
        "severity",
        "severity_label",
        "diseases",
        "disease_diabetes",
        "disease_ckd",
        "disease_heart_failure",
        "disease_hypertension",
        "smiles_a",
        "smiles_b",
        "source_rows",
        "pair_drug_1_norm",
        "pair_drug_2_norm",
    ]
    pairs[columns].to_csv(output_dir / "polyguard_severity_pairs.csv", index=False)
    write_summary(pairs, output_dir / "polyguard_severity_pairs_summary.md")
    print(f"Wrote {len(pairs)} rows to {output_dir / 'polyguard_severity_pairs.csv'}")


if __name__ == "__main__":
    main()
