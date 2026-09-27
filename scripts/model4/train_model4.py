"""
Model 4 (research branch) - Step 4: train + evaluate end-to-end, using the
SAME two protocols as Model 1 (scripts/train_eval_severity_model.py) on the
SAME 48,784-pair subset, so the comparison is apples-to-apples:
  - "standard": 70/30 stratified split
  - "cold_start": 20% of drugs held out entirely from training

The interaction graph used for GraphSAGE message passing is built ONLY from
training-split pairs, in both protocols - test pairs are never added as
edges, so message passing cannot see the label it's being evaluated on.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from rdkit import Chem
from rdkit.Chem import Descriptors
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.utils.class_weight import compute_class_weight
from torch_geometric.data import Batch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model4_architecture import Model4DDIPredictor  # noqa: E402
from molecular_graph import smiles_to_graph  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "model4"
SEVERITY_ORDER = ["Minor", "Moderate", "Major"]
SEVERITY_TO_IDX = {s: i for i, s in enumerate(SEVERITY_ORDER)}
RANDOM_STATE = 42


def physchem_features(mol: Chem.Mol) -> list[float]:
    return [
        Descriptors.MolWt(mol) / 500.0,
        Descriptors.MolLogP(mol) / 5.0,
        Descriptors.TPSA(mol) / 150.0,
        float(Descriptors.NumHDonors(mol)) / 5.0,
        float(Descriptors.NumHAcceptors(mol)) / 10.0,
    ]


def build_node_data():
    nodes = pd.read_csv(OUT_DIR / "model4_nodes.csv")
    kg_emb = torch.load(OUT_DIR / "kg_entity_embeddings.pt")
    kg_idx = json.load(open(OUT_DIR / "kg_entity_to_idx.json", encoding="utf-8"))

    graphs, kg_rows, physchem_rows = [], [], []
    for row in nodes.itertuples():
        mol = Chem.MolFromSmiles(row.smiles)
        graphs.append(smiles_to_graph(row.smiles))
        physchem_rows.append(physchem_features(mol))
        kg_rows.append(kg_emb[kg_idx[f"Compound::{row.drugbank_id}"]])

    mol_batch = Batch.from_data_list(graphs)
    kg_features = torch.stack(kg_rows)
    physchem = torch.tensor(physchem_rows, dtype=torch.float)
    return nodes, mol_batch, kg_features, physchem


def build_edge_index(train_df: pd.DataFrame, num_nodes: int) -> torch.Tensor:
    a = train_df["node_a"].to_numpy()
    b = train_df["node_b"].to_numpy()
    src = np.concatenate([a, b])
    dst = np.concatenate([b, a])
    return torch.tensor(np.stack([src, dst]), dtype=torch.long)


def evaluate(model, node_embeddings, kg_features, df) -> dict:
    idx_a = torch.tensor(df["node_a"].to_numpy(), dtype=torch.long)
    idx_b = torch.tensor(df["node_b"].to_numpy(), dtype=torch.long)
    with torch.no_grad():
        logits = model.predict_pairs(node_embeddings, kg_features, idx_a, idx_b)
    y_pred = [SEVERITY_ORDER[i] for i in logits.argmax(dim=-1).tolist()]
    y_true = df["severity"].tolist()
    report = classification_report(y_true, y_pred, labels=SEVERITY_ORDER, output_dict=True, zero_division=0)
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "n": len(df),
        "per_class_f1": {label: report[label]["f1-score"] for label in SEVERITY_ORDER},
    }


def run_protocol(label: str, train_df: pd.DataFrame, test_df: pd.DataFrame,
                  mol_batch, kg_features, physchem, num_nodes: int, epochs: int) -> dict:
    print(f"\n=== Model 4 - {label} protocol ===")
    print(f"Train pairs: {len(train_df)} | Test pairs: {len(test_df)}")

    edge_index = build_edge_index(train_df, num_nodes)
    model = Model4DDIPredictor(kg_dim=kg_features.shape[1])
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    y_train_idx = torch.tensor(train_df["severity"].map(SEVERITY_TO_IDX).to_numpy(), dtype=torch.long)
    class_weights = compute_class_weight("balanced", classes=np.arange(3), y=y_train_idx.numpy())
    class_weights_t = torch.tensor(class_weights, dtype=torch.float)

    idx_a_train = torch.tensor(train_df["node_a"].to_numpy(), dtype=torch.long)
    idx_b_train = torch.tensor(train_df["node_b"].to_numpy(), dtype=torch.long)

    model.train()
    t0 = time.time()
    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        node_embeddings = model.encode_nodes(mol_batch, kg_features, physchem, edge_index)
        logits = model.predict_pairs(node_embeddings, kg_features, idx_a_train, idx_b_train)
        loss = F.cross_entropy(logits, y_train_idx, weight=class_weights_t)
        loss.backward()
        optimizer.step()
        if epoch == 1 or epoch % 5 == 0 or epoch == epochs:
            print(f"  epoch {epoch:3d}/{epochs}  loss {loss.item():.4f}  ({time.time()-t0:.0f}s elapsed)")

    model.eval()
    with torch.no_grad():
        node_embeddings = model.encode_nodes(mol_batch, kg_features, physchem, edge_index)
    metrics = evaluate(model, node_embeddings, kg_features, test_df)

    torch.save(model.state_dict(), OUT_DIR / f"model4_{label}.pt")
    print(f"Saved trained weights to model4_{label}.pt")

    majority_class = train_df["severity"].value_counts().idxmax()
    majority_pred = [majority_class] * len(test_df)
    majority_metrics = {
        "accuracy": accuracy_score(test_df["severity"], majority_pred),
        "macro_f1": f1_score(test_df["severity"], majority_pred, average="macro"),
    }

    print(f"Majority-class baseline -> accuracy {majority_metrics['accuracy']:.4f}  macro-F1 {majority_metrics['macro_f1']:.4f}")
    print(f"Model 4 ({label})        -> accuracy {metrics['accuracy']:.4f}  macro-F1 {metrics['macro_f1']:.4f}  per-class F1 {metrics['per_class_f1']}")

    return {"model4": metrics, "majority_baseline": majority_metrics}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()

    print("Building node data (molecular graphs + KG features + physchem descriptors)...")
    nodes, mol_batch, kg_features, physchem = build_node_data()
    num_nodes = len(nodes)
    print(f"Nodes: {num_nodes}")

    results = {}
    for label, train_name, test_name in [
        ("standard", "model4_train_standard.csv", "model4_test_standard.csv"),
        ("cold_start", "model4_train_coldstart.csv", "model4_test_coldstart.csv"),
    ]:
        train_df = pd.read_csv(OUT_DIR / train_name)
        test_df = pd.read_csv(OUT_DIR / test_name)
        results[label] = run_protocol(label, train_df, test_df, mol_batch, kg_features, physchem, num_nodes, args.epochs)

    with open(OUT_DIR / "model4_eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {OUT_DIR / 'model4_eval_results.json'}")


if __name__ == "__main__":
    main()
