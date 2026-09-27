"""
Model 4 (research branch) - molecular graph construction + GATv2 encoder.

Converts a drug's SMILES string into a PyTorch Geometric graph (atoms as
nodes, bonds as edges) and defines a shared-weight GATv2 encoder that maps
that graph to a fixed-size drug embedding, matching panel 3A of the
architecture diagram ("Molecular Graph Construction & Encoding").

This is intentionally a lighter GATv2 than a full pretrained chemistry
foundation model - PolyGuard already tried a heavier fingerprint-based
chemistry model (Model 2) and it underperformed on cold-start pairs, so this
component's job here is to feed the same signal in a form the diagram's
downstream co-attention/fusion stage can use, not to relitigate that result.
"""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn.functional as F
from rdkit import Chem
from torch_geometric.data import Data
from torch_geometric.nn import GATv2Conv, global_mean_pool

# --- Atom featurization (small, interpretable feature set) ---
ATOM_LIST = ["C", "N", "O", "S", "F", "Cl", "Br", "I", "P", "H"]


def atom_features(atom: Chem.Atom) -> list[float]:
    symbol = atom.GetSymbol()
    one_hot = [1.0 if symbol == s else 0.0 for s in ATOM_LIST]
    other = 1.0 if symbol not in ATOM_LIST else 0.0
    return one_hot + [
        other,
        atom.GetDegree() / 4.0,
        atom.GetFormalCharge(),
        1.0 if atom.GetIsAromatic() else 0.0,
        atom.GetTotalNumHs() / 4.0,
    ]


ATOM_FEATURE_DIM = len(ATOM_LIST) + 5


def smiles_to_graph(smiles: str) -> Data | None:
    """Parse a SMILES string into a PyG Data graph, or None if invalid."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        return None

    xs = [atom_features(atom) for atom in mol.GetAtoms()]
    x = torch.tensor(xs, dtype=torch.float)

    edge_index = []
    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edge_index.append([i, j])
        edge_index.append([j, i])
    if not edge_index:
        # Single-atom molecule (e.g. some ions): add a self-loop so GATv2 has an edge to work with.
        edge_index = [[0, 0]]
    edge_index_t = torch.tensor(edge_index, dtype=torch.long).t().contiguous()

    return Data(x=x, edge_index=edge_index_t)


class MolecularGATv2Encoder(torch.nn.Module):
    """Shared-weight GATv2 encoder: molecular graph -> fixed-size drug embedding."""

    def __init__(self, in_dim: int = ATOM_FEATURE_DIM, hidden_dim: int = 64, out_dim: int = 128, heads: int = 4):
        super().__init__()
        self.conv1 = GATv2Conv(in_dim, hidden_dim, heads=heads, concat=True)
        self.conv2 = GATv2Conv(hidden_dim * heads, hidden_dim, heads=heads, concat=True)
        self.proj = torch.nn.Linear(hidden_dim * heads, out_dim)

    def forward(self, x, edge_index, batch):
        h = F.elu(self.conv1(x, edge_index))
        h = F.elu(self.conv2(h, edge_index))
        h = global_mean_pool(h, batch)  # graph-level embedding
        return self.proj(h)

    def forward_with_attention(self, x, edge_index, batch):
        """Same forward pass but also returns layer-2 attention weights per edge,
        for the molecular explainability panel (10.1 in the diagram)."""
        h, (edge_index_att, alpha1) = self.conv1(x, edge_index, return_attention_weights=True)
        h = F.elu(h)
        h, (_, alpha2) = self.conv2(h, edge_index, return_attention_weights=True)
        h = F.elu(h)
        pooled = global_mean_pool(h, batch)
        out = self.proj(pooled)
        return out, edge_index_att, alpha2
