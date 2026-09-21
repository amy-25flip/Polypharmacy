from __future__ import annotations

import argparse
import ast
import csv
from pathlib import Path

import pandas as pd


SEVERITY_ORDER = {"Minor": 0, "Moderate": 1, "Major": 2, "Unknown": ""}
OUTPUT_COLUMNS = [
    "source",
    "record_type",
    "n_drugs",
    "drug_ids",
    "drug_names",
    "smiles",
    "label_type",
    "label_value",
    "severity",
    "severity_label",
    "disease_scope",
    "disease_diabetes",
    "disease_ckd",
    "disease_heart_failure",
    "disease_hypertension",
    "outcome_id",
    "binary_label",
    "age",
    "condition",
    "serious",
    "prr",
    "ci_lower",
    "ci_upper",
    "p_value",
    "reports_count",
    "source_record_id",
    "entity_a",
    "relation",
    "entity_b",
    "entity_a_name",
    "entity_kind",
]


def disease_flags(scope: object) -> dict[str, int]:
    text = "" if pd.isna(scope) else str(scope)
    diseases = {item.strip().lower() for item in text.split("|")}
    return {
        "disease_diabetes": int("diabetes" in diseases),
        "disease_ckd": int("kidney disease" in diseases or "ckd" in diseases),
        "disease_heart_failure": int("heart failure" in diseases or "heart disease" in diseases),
        "disease_hypertension": int("hypertension" in diseases),
    }


def base_row(**values: object) -> dict[str, object]:
    row = {column: "" for column in OUTPUT_COLUMNS}
    row.update({key: value for key, value in values.items() if key in row})
    return row


def parse_drugbank_ids(value: object) -> list[str]:
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def load_smiles_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    if not {"drugbank_id", "smiles"}.issubset(df.columns):
        return {}
    df = df.dropna(subset=["drugbank_id", "smiles"])
    return dict(zip(df["drugbank_id"].astype(str), df["smiles"].astype(str)))


def append_rows(path: Path, rows: list[dict[str, object]], *, write_header: bool) -> bool:
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        if write_header:
            writer.writeheader()
            write_header = False
        writer.writerows(rows)
    return write_header


def merge_ddinter_scoped(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "ddinter_4diseases_filtered.csv"
    rows_written = 0
    for chunk in pd.read_csv(path, chunksize=100_000):
        rows = []
        chunk = chunk[chunk["Level"].isin(SEVERITY_ORDER)]
        for item in chunk.itertuples(index=False):
            flags = disease_flags(item.Diseases)
            rows.append(
                base_row(
                    source="DDInter",
                    record_type="pair",
                    n_drugs=2,
                    drug_ids=f"{item.DDInterID_A}|{item.DDInterID_B}",
                    drug_names=f"{item.Drug_A}|{item.Drug_B}",
                    label_type="severity_tier",
                    label_value=item.Level,
                    severity=item.Level,
                    severity_label=SEVERITY_ORDER[item.Level],
                    disease_scope=item.Diseases,
                    source_record_id=f"{item.DDInterID_A}|{item.DDInterID_B}",
                    **flags,
                )
            )
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def merge_ddinter_all(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "ddinter_all_combined.csv"
    rows_written = 0
    for chunk in pd.read_csv(path, chunksize=100_000):
        rows = []
        chunk = chunk[chunk["Level"].isin(SEVERITY_ORDER)]
        for item in chunk.itertuples(index=False):
            rows.append(
                base_row(
                    source="DDInter_all",
                    record_type="pair",
                    n_drugs=2,
                    drug_ids=f"{item.DDInterID_A}|{item.DDInterID_B}",
                    drug_names=f"{item.Drug_A}|{item.Drug_B}",
                    label_type="severity_tier",
                    label_value=item.Level,
                    severity=item.Level,
                    severity_label=SEVERITY_ORDER[item.Level],
                    source_record_id=f"{item.DDInterID_A}|{item.DDInterID_B}",
                )
            )
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def merge_drugbank(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "DrugBank.csv"
    rows_written = 0
    for chunk in pd.read_csv(path, chunksize=100_000):
        rows = []
        for item in chunk.itertuples(index=False):
            rows.append(
                base_row(
                    source="DrugBank",
                    record_type="pair",
                    n_drugs=2,
                    drug_ids=f"{item.Drug1_ID}|{item.Drug2_ID}",
                    smiles=f"{item.Drug1}|{item.Drug2}",
                    label_type="interaction_type_id",
                    label_value=item.Y,
                    source_record_id=f"{item.Drug1_ID}|{item.Drug2_ID}|{item.Y}",
                )
            )
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def merge_twosides(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "TWOSIDES.csv"
    rows_written = 0
    for chunk in pd.read_csv(path, chunksize=100_000):
        rows = []
        for item in chunk.itertuples(index=False):
            rows.append(
                base_row(
                    source="TWOSIDES",
                    record_type="pair",
                    n_drugs=2,
                    drug_ids=f"{item.Drug1_ID}|{item.Drug2_ID}",
                    smiles=f"{item.Drug1}|{item.Drug2}",
                    label_type="side_effect_id",
                    label_value=item.Y,
                    outcome_id=item.Y,
                    source_record_id=f"{item.Drug1_ID}|{item.Drug2_ID}|{item.Y}",
                )
            )
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def merge_hoddi(data_dir: Path, output_path: Path, write_header: bool, smiles_by_id: dict[str, str]) -> tuple[bool, int]:
    rows_written = 0
    for drug_count in [3, 4, 5]:
        for polarity, filename in [("positive", f"{drug_count}_drug.csv"), ("negative", f"{drug_count}_drugnegative.csv")]:
            path = data_dir / filename
            for chunk in pd.read_csv(path, chunksize=100_000):
                rows = []
                for _, item in chunk.iterrows():
                    drug_ids = parse_drugbank_ids(item["DrugBankID"])
                    smiles = [smiles_by_id.get(drug_id, "") for drug_id in drug_ids]
                    rows.append(
                        base_row(
                            source=f"HODDI_{polarity}",
                            record_type="hyperedge",
                            n_drugs=len(drug_ids) or drug_count,
                            drug_ids="|".join(drug_ids),
                            smiles="|".join(smiles),
                            label_type="higher_order_adverse_event",
                            label_value=item["SE_above_0.9"],
                            outcome_id=item["SE_above_0.9"],
                            binary_label=item["hyperedge_label"],
                            age=item["age"],
                            condition=item["condition"],
                            serious=item["serious"],
                            prr=item["prr"],
                            ci_lower=item["ci_lower"],
                            ci_upper=item["ci_upper"],
                            p_value=item["p_value"],
                            reports_count=item["reports_count"],
                            source_record_id=item["report_id"],
                        )
                    )
                write_header = append_rows(output_path, rows, write_header=write_header)
                rows_written += len(rows)
    return write_header, rows_written


def merge_hetionet_nodes(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "hetionet-v1.0-nodes.tsv"
    rows_written = 0
    for chunk in pd.read_csv(path, sep="\t", chunksize=100_000):
        rows = [
            base_row(
                source="Hetionet",
                record_type="knowledge_graph_node",
                label_type="node_kind",
                label_value=item.kind,
                entity_a=item.id,
                entity_a_name=item.name,
                entity_kind=item.kind,
                source_record_id=item.id,
            )
            for item in chunk.itertuples(index=False)
        ]
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def merge_hetionet_edges(data_dir: Path, output_path: Path, write_header: bool) -> tuple[bool, int]:
    path = data_dir / "edges.sif"
    rows_written = 0
    for chunk in pd.read_csv(path, sep="\t", chunksize=100_000):
        rows = [
            base_row(
                source="Hetionet",
                record_type="knowledge_graph_edge",
                label_type="kg_relation",
                label_value=item.metaedge,
                entity_a=item.source,
                relation=item.metaedge,
                entity_b=item.target,
                source_record_id=f"{item.source}|{item.metaedge}|{item.target}",
            )
            for item in chunk.itertuples(index=False)
        ]
        write_header = append_rows(output_path, rows, write_header=write_header)
        rows_written += len(rows)
    return write_header, rows_written


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge PolyGuard source datasets into one normalized ML evidence CSV.")
    parser.add_argument("--data-dir", type=Path, default=Path(r"E:\Polypharmacy\Datasets"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"E:\Polypharmacy\processed"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "polyguard_merged_ml_dataset.csv"
    if output_path.exists():
        output_path.unlink()

    smiles_by_id = load_smiles_map(args.data_dir / "DrugBankID2SMILES.csv")
    write_header = True
    counts: dict[str, int] = {}

    mergers = [
        ("ddinter_scoped", lambda: merge_ddinter_scoped(args.data_dir, output_path, write_header)),
        ("ddinter_all", lambda: merge_ddinter_all(args.data_dir, output_path, write_header)),
        ("drugbank", lambda: merge_drugbank(args.data_dir, output_path, write_header)),
        ("twosides", lambda: merge_twosides(args.data_dir, output_path, write_header)),
        ("hoddi", lambda: merge_hoddi(args.data_dir, output_path, write_header, smiles_by_id)),
        ("hetionet_nodes", lambda: merge_hetionet_nodes(args.data_dir, output_path, write_header)),
        ("hetionet_edges", lambda: merge_hetionet_edges(args.data_dir, output_path, write_header)),
    ]

    for name, merge in mergers:
        write_header, count = merge()
        counts[name] = count
        print(f"{name}: {count}")

    summary_path = args.output_dir / "polyguard_merged_ml_dataset_summary.md"
    lines = ["# PolyGuard merged ML evidence dataset", "", f"Output: {output_path}", "", "Rows by source:"]
    lines.extend(f"- {name}: {count}" for name, count in counts.items())
    lines.extend(
        [
            "",
            "How to use this file:",
            "- Train the severity classifier on rows where label_type == 'severity_tier'.",
            "- Use HODDI hyperedge rows for the multi-drug/regimen model path.",
            "- Use DrugBank/TWOSIDES rows as auxiliary pairwise interaction and side-effect signals.",
            "- Use Hetionet rows as knowledge-graph feature data, not as severity labels.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote merged CSV: {output_path}")
    print(f"Wrote summary: {summary_path}")


if __name__ == "__main__":
    main()
