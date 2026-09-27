"""
Model 4 (research branch) - Step 1: extract a compound/disease-relevant subgraph
from the full Hetionet edge list for knowledge-graph embedding training.

Why a subgraph and not all 2.25M Hetionet edges: the majority of Hetionet's
edges describe gene/protein biology (GpBP, GpMF, GpPW, GpCC, AeG, AuG, AdG,
GiG, Gr>G - gene ontology, anatomy expression, gene regulation) which is not
directly load-bearing for compound-compound interaction reasoning, and
including it would blow up CPU-only TransE training time by >10x for little
benefit to this task. We keep every relation type that can appear on a path
between two drugs or between a drug and something clinically relevant
(gene target, side effect, pharmacologic class, disease), matching the same
edge scope the existing explainability engine already reasons over
(CbG, CcSE, PCiC, CrC) plus a few more that extend the same kind of path
(CdG, CuG, CtD, CpD, disease-gene/anatomy/symptom edges) so the embedding
space is consistent with what PolyGuard already tells doctors.

This is a documented, deliberate scoping decision for a course-project
research branch, not an oversight.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = PROJECT_ROOT / "Datasets"
OUT_DIR = PROJECT_ROOT / "processed" / "model4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Relation types kept for the KG-embedding subgraph (see module docstring).
KEEP_METAEDGES = {
    "CbG",   # Compound - binds - Gene
    "CcSE",  # Compound - causes - Side Effect
    "PCiC",  # Pharmacologic Class - includes - Compound
    "CrC",   # Compound - resembles - Compound
    "CdG",   # Compound - downregulates - Gene
    "CuG",   # Compound - upregulates - Gene
    "CtD",   # Compound - treats - Disease
    "CpD",   # Compound - palliates - Disease
    "DaG",   # Disease - associates - Gene
    "DuG",   # Disease - upregulates - Gene
    "DdG",   # Disease - downregulates - Gene
    "DpS",   # Disease - presents - Symptom
    "DrD",   # Disease - resembles - Disease
    "DlA",   # Disease - localizes - Anatomy
}


def main() -> None:
    print("Loading full Hetionet edge list...")
    edges = pd.read_csv(DATASETS_DIR / "edges.sif", sep="\t")
    edges.columns = ["source", "metaedge", "target"]

    subset = edges[edges["metaedge"].isin(KEEP_METAEDGES)].copy()
    print(f"Kept {len(subset):,} / {len(edges):,} edges across {subset['metaedge'].nunique()} relation types.")

    nodes = pd.read_csv(DATASETS_DIR / "hetionet-v1.0-nodes.tsv", sep="\t")
    id_to_name = dict(zip(nodes["id"], nodes["name"]))
    subset["source_name"] = subset["source"].map(id_to_name)
    subset["target_name"] = subset["target"].map(id_to_name)

    triples_path = OUT_DIR / "kg_triples.tsv"
    subset[["source", "metaedge", "target"]].to_csv(triples_path, sep="\t", index=False, header=False)
    print(f"Wrote {triples_path} ({len(subset):,} triples).")

    entities = pd.unique(subset[["source", "target"]].values.ravel("K"))
    print(f"Entities in subgraph: {len(entities):,}")

    compounds_in_subgraph = {e for e in entities if e.startswith("Compound::")}
    print(f"Compound (drug) nodes reachable in this subgraph: {len(compounds_in_subgraph):,}")

    summary_path = OUT_DIR / "kg_triples_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Model 4 KG-embedding subgraph summary\n\n")
        f.write(f"- Source: `Datasets/edges.sif` (full Hetionet, {len(edges):,} edges)\n")
        f.write(f"- Kept relation types: {sorted(KEEP_METAEDGES)}\n")
        f.write(f"- Triples kept: {len(subset):,}\n")
        f.write(f"- Entities: {len(entities):,}\n")
        f.write(f"- Compound (drug) nodes reachable: {len(compounds_in_subgraph):,}\n\n")
        f.write("## Triples per relation type\n\n")
        f.write(subset["metaedge"].value_counts().to_string())
        f.write("\n")
    print(f"Wrote {summary_path}.")


if __name__ == "__main__":
    main()
