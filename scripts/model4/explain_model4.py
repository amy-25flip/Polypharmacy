"""
Model 4 (research branch) - multi-level explainability, matching diagram
panels 10.1-10.3 (10.4 patient-SHAP is out of scope, see model4_architecture.py
docstring).

10.1 Molecular Explainability: per-atom GAT attention weights from the
     trained GATv2 encoder for a given drug's molecule.
10.2 Interaction Graph Explainability: which OTHER drugs in the known
     interaction graph most influenced this drug's message-passed embedding
     (ranked by GraphSAGE-neighborhood contribution).
10.3 Knowledge Graph Explainability: reuses the project's existing Hetionet
     path-based reasoning (explainability.py) - the KG embedding used inside
     Model 4 is not itself a human-readable "path", so path explanations
     still come from the rule-based engine, same as production.

This is a diagnostic/reporting script, not part of the live API - it loads
the Model 4 checkpoint (if trained/saved) and prints explanations for a
given drug pair.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import torch
from rdkit import Chem
from rdkit.Chem import Descriptors
from torch_geometric.data import Batch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model4_architecture import Model4DDIPredictor  # noqa: E402
from molecular_graph import smiles_to_graph  # noqa: E402
from train_model4 import build_edge_index, build_node_data  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "processed" / "model4"
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]


def molecular_attention(model: Model4DDIPredictor, smiles: str) -> list[dict]:
    """Panel 10.1: per-atom attention weight (averaged over heads, layer 2)."""
    mol = Chem.MolFromSmiles(smiles)
    graph = smiles_to_graph(smiles)
    batch = Batch.from_data_list([graph])
    with torch.no_grad():
        _, edge_index_att, alpha = model.mol_encoder.forward_with_attention(batch.x, batch.edge_index, batch.batch)
    alpha_mean = alpha.mean(dim=-1)  # average over attention heads

    atom_scores = torch.zeros(graph.x.shape[0])
    atom_counts = torch.zeros(graph.x.shape[0])
    for e in range(edge_index_att.shape[1]):
        target = edge_index_att[1, e].item()
        atom_scores[target] += alpha_mean[e]
        atom_counts[target] += 1
    atom_scores = atom_scores / atom_counts.clamp(min=1)

    result = []
    for i, atom in enumerate(mol.GetAtoms()):
        result.append({"atom_idx": i, "symbol": atom.GetSymbol(), "attention": round(atom_scores[i].item(), 4)})
    return sorted(result, key=lambda r: -r["attention"])


def interaction_graph_neighbors(nodes: pd.DataFrame, train_pairs: pd.DataFrame, drug_name: str, top_k: int = 5) -> list[dict]:
    """Panel 10.2: which neighbors in the training interaction graph this drug
    is directly connected to, ranked by how many documented pairs (of any
    severity) connect them - a proxy for how much message-passing weight
    that neighbor contributes to this drug's refined embedding."""
    node_row = nodes[nodes["drug_name"] == drug_name]
    if node_row.empty:
        return []
    node_idx = int(node_row.iloc[0]["node_idx"])

    neighbor_rows = train_pairs[(train_pairs["node_a"] == node_idx) | (train_pairs["node_b"] == node_idx)]
    neighbor_counts: dict[str, int] = {}
    for row in neighbor_rows.itertuples():
        other = row.drug_b if row.drug_a == drug_name else row.drug_a
        neighbor_counts[other] = neighbor_counts.get(other, 0) + 1

    ranked = sorted(neighbor_counts.items(), key=lambda kv: -kv[1])[:top_k]
    total = sum(neighbor_counts.values()) or 1
    return [{"neighbor": name, "shared_edges": count, "weight": round(count / total, 3)} for name, count in ranked]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("drug_a", type=str)
    parser.add_argument("drug_b", type=str)
    args = parser.parse_args()

    nodes = pd.read_csv(OUT_DIR / "model4_nodes.csv")
    train_pairs = pd.read_csv(OUT_DIR / "model4_train_standard.csv")

    row_a = nodes[nodes["drug_name"] == args.drug_a]
    row_b = nodes[nodes["drug_name"] == args.drug_b]
    if row_a.empty or row_b.empty:
        print(f"One or both drugs not in Model 4's {len(nodes)}-drug coverage set "
              f"(needs both SMILES and a Hetionet KG node). Try `python -c \"import pandas as pd; "
              f"print(pd.read_csv('processed/model4/model4_nodes.csv')['drug_name'].tolist())\"` to list coverage.")
        return

    print("Loading trained Model 4 (standard protocol checkpoint) and node data...")
    _, mol_batch, kg_features, physchem = build_node_data()
    model = Model4DDIPredictor(kg_dim=kg_features.shape[1])
    checkpoint_path = OUT_DIR / "model4_standard.pt"
    if checkpoint_path.exists():
        model.load_state_dict(torch.load(checkpoint_path, map_location="cpu"))
    else:
        print(f"WARNING: no checkpoint at {checkpoint_path} - using untrained weights. "
              f"Run train_model4.py first for meaningful explanations.")
    edge_index = build_edge_index(train_pairs, len(nodes))
    model.eval()

    print(f"\n--- Panel 10.1: Molecular Explainability (GAT attention) for {args.drug_a} ---")
    for atom in molecular_attention(model, row_a.iloc[0]["smiles"])[:5]:
        print(f"  atom {atom['atom_idx']:>3} ({atom['symbol']:>2})  attention={atom['attention']}")

    print(f"\n--- Panel 10.2: Interaction Graph Explainability for {args.drug_a} ---")
    for n in interaction_graph_neighbors(nodes, train_pairs, args.drug_a):
        print(f"  {n['neighbor']:<30} shared_edges={n['shared_edges']}  weight={n['weight']}")

    print("\n(Panel 10.3 Knowledge Graph Explainability reuses webapp/explainability.py, "
          "the same Hetionet path-reasoning already in production.)")


if __name__ == "__main__":
    main()
