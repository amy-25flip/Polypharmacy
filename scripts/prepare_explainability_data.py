from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

NODES_PATH = Path(r"E:\Polypharmacy\Datasets\hetionet-v1.0-nodes.tsv")
EDGES_PATH = Path(r"E:\Polypharmacy\Datasets\edges.sif")
NAME_TO_ID_PATH = Path(r"E:\Polypharmacy\processed\drug_name_to_drugbank_id.json")
OUTPUT_PATH = Path(r"E:\Polypharmacy\processed\explainability_data.json")


def strip_prefix(value: str) -> str:
    return value.split("::", 1)[1] if "::" in value else value


def main() -> None:
    nodes = pd.read_csv(NODES_PATH, sep="\t")
    id_to_name = dict(zip(nodes["id"], nodes["name"]))

    edges = pd.read_csv(EDGES_PATH, sep="\t")

    with open(NAME_TO_ID_PATH, encoding="utf-8") as f:
        name_to_drugbank_id = json.load(f)
    our_drugbank_ids = set(name_to_drugbank_id.values())

    def build_drug_to_items(metaedge: str, source_is_drug: bool) -> dict[str, list[str]]:
        sub = edges[edges["metaedge"] == metaedge]
        drug_to_items: dict[str, set[str]] = defaultdict(set)
        for _, row in sub.iterrows():
            drug_full = row["source"] if source_is_drug else row["target"]
            item_full = row["target"] if source_is_drug else row["source"]
            if not drug_full.startswith("Compound::"):
                continue
            drug_id = strip_prefix(drug_full)
            if drug_id not in our_drugbank_ids:
                continue
            drug_to_items[drug_id].add(item_full)
        return {k: sorted(v) for k, v in drug_to_items.items()}

    genes = build_drug_to_items("CbG", source_is_drug=True)
    side_effects = build_drug_to_items("CcSE", source_is_drug=True)
    classes = build_drug_to_items("PCiC", source_is_drug=False)  # PCiC: class -> drug

    resembles: dict[str, list[str]] = defaultdict(list)
    crc = edges[edges["metaedge"] == "CrC"]
    for _, row in crc.iterrows():
        a, b = strip_prefix(row["source"]), strip_prefix(row["target"])
        if a in our_drugbank_ids and b in our_drugbank_ids:
            resembles[a].append(b)
            resembles[b].append(a)
    resembles = {k: sorted(set(v)) for k, v in resembles.items()}

    def idf_weights(drug_to_items: dict[str, list[str]]) -> dict[str, float]:
        item_drug_count: dict[str, int] = defaultdict(int)
        for items in drug_to_items.values():
            for item in items:
                item_drug_count[item] += 1
        total_drugs = max(len(drug_to_items), 1)
        return {
            item: round(math.log(total_drugs / count), 4)
            for item, count in item_drug_count.items()
        }

    gene_weights = idf_weights(genes)
    side_effect_weights = idf_weights(side_effects)
    class_weights = idf_weights(classes)

    # gene/side-effect/class dict values are already the full "Kind::code" node id
    # (e.g. "Side Effect::C1291077"), so this is a direct lookup, not a re-prefixed one.
    item_names = {
        item_id: id_to_name.get(item_id, item_id)
        for item_id in set(gene_weights) | set(side_effect_weights) | set(class_weights)
    }

    output = {
        "genes": genes,
        "side_effects": side_effects,
        "classes": classes,
        "resembles": resembles,
        "gene_weights": gene_weights,
        "side_effect_weights": side_effect_weights,
        "class_weights": class_weights,
        "item_names": item_names,
    }

    OUTPUT_PATH.write_text(json.dumps(output), encoding="utf-8")

    print(f"Drugs with gene/target data: {len(genes)}")
    print(f"Drugs with side-effect data: {len(side_effects)}")
    print(f"Drugs with pharmacologic-class data: {len(classes)}")
    print(f"Drugs with structural-resemblance data: {len(resembles)}")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
