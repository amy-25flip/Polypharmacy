"""
Model 4 (research branch) - full architecture, matching the team's diagram:

  3A molecular GATv2 encoder (molecular_graph.py)
  3B knowledge-graph embedding (pretrained TransE, loaded here)
  4/5 drug-interaction graph + GraphSAGE message passing
  5  symmetric co-attention between the query pair
  7  multi-modal feature fusion
  8  bilinear decoder
  9  prediction head (severity classification)

Panel 3C (patient clinical features) is intentionally NOT part of this
module - see the project's memory/README notes on why (no real patient-drug-
outcome dataset exists to train it on; it's handled separately as a
transparent rule-based modifier, not a trained branch).
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv

from molecular_graph import MolecularGATv2Encoder


class InteractionGraphGNN(torch.nn.Module):
    """Panel 5: refines each drug's node embedding using its neighbors in the
    known drug-interaction graph (2-layer GraphSAGE)."""

    def __init__(self, dim: int = 128):
        super().__init__()
        self.conv1 = SAGEConv(dim, dim)
        self.conv2 = SAGEConv(dim, dim)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        h = self.conv2(h, edge_index)
        return h


class CoAttention(torch.nn.Module):
    """Panel 5 (co-attention): symmetric single-head scaled dot-product
    cross-attention between the two drugs in a query pair - each drug's
    representation is refined by attending to the other's."""

    def __init__(self, dim: int = 128):
        super().__init__()
        self.q_proj = torch.nn.Linear(dim, dim)
        self.k_proj = torch.nn.Linear(dim, dim)
        self.scale = dim ** 0.5

    def forward(self, h_a: torch.Tensor, h_b: torch.Tensor):
        q_a, k_a = self.q_proj(h_a), self.k_proj(h_a)
        q_b, k_b = self.q_proj(h_b), self.k_proj(h_b)
        # a attends to b, b attends to a (single "token" each -> scalar attention weight,
        # but keep the general form so it degrades gracefully / is easy to extend).
        attn_ab = torch.sigmoid((q_a * k_b).sum(-1, keepdim=True) / self.scale)
        attn_ba = torch.sigmoid((q_b * k_a).sum(-1, keepdim=True) / self.scale)
        z_a = h_a + attn_ab * h_b
        z_b = h_b + attn_ba * h_a
        return z_a, z_b


class BilinearDecoder(torch.nn.Module):
    """Panel 8: s_bilinear = z_A^T W_b z_B, one scalar score per output class."""

    def __init__(self, dim: int = 128, num_classes: int = 3):
        super().__init__()
        self.W = torch.nn.Parameter(torch.empty(num_classes, dim, dim))
        torch.nn.init.xavier_uniform_(self.W)

    def forward(self, z_a: torch.Tensor, z_b: torch.Tensor) -> torch.Tensor:
        # (batch, dim) x (classes, dim, dim) x (batch, dim) -> (batch, classes)
        return torch.einsum("bi,cij,bj->bc", z_a, self.W, z_b)


class Model4DDIPredictor(torch.nn.Module):
    """End-to-end: molecular graphs + KG embeddings -> interaction-graph GNN ->
    co-attention -> multi-modal fusion + bilinear decoder -> severity logits."""

    SEVERITY_ORDER = ["Minor", "Moderate", "Major"]

    def __init__(self, kg_dim: int = 128, node_dim: int = 128, physchem_dim: int = 5):
        super().__init__()
        self.mol_encoder = MolecularGATv2Encoder(out_dim=node_dim)
        self.node_fuse = torch.nn.Sequential(
            torch.nn.Linear(node_dim + kg_dim + physchem_dim, node_dim),
            torch.nn.ReLU(),
            torch.nn.Linear(node_dim, node_dim),
        )
        self.interaction_gnn = InteractionGraphGNN(dim=node_dim)
        self.co_attention = CoAttention(dim=node_dim)
        self.fusion = torch.nn.Sequential(
            torch.nn.Linear(node_dim * 2 + kg_dim * 2, node_dim),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.2),
        )
        self.bilinear = BilinearDecoder(dim=node_dim, num_classes=len(self.SEVERITY_ORDER))
        self.head = torch.nn.Sequential(
            torch.nn.Linear(node_dim + len(self.SEVERITY_ORDER), 64),
            torch.nn.ReLU(),
            torch.nn.Linear(64, len(self.SEVERITY_ORDER)),
        )

    def encode_nodes(self, mol_batch, kg_features: torch.Tensor, physchem: torch.Tensor,
                      interaction_edge_index: torch.Tensor) -> torch.Tensor:
        """Compute refined embeddings for ALL drug nodes (call once per forward pass,
        not per pair - the interaction-graph message passing needs every node)."""
        mol_emb = self.mol_encoder(mol_batch.x, mol_batch.edge_index, mol_batch.batch)
        node0 = self.node_fuse(torch.cat([mol_emb, kg_features, physchem], dim=-1))
        return self.interaction_gnn(node0, interaction_edge_index)

    def predict_pairs(self, node_embeddings: torch.Tensor, kg_features: torch.Tensor,
                       idx_a: torch.Tensor, idx_b: torch.Tensor) -> torch.Tensor:
        h_a, h_b = node_embeddings[idx_a], node_embeddings[idx_b]
        k_a, k_b = kg_features[idx_a], kg_features[idx_b]
        z_a, z_b = self.co_attention(h_a, h_b)
        f_pair = self.fusion(torch.cat([z_a, z_b, k_a, k_b], dim=-1))
        s_bilinear = self.bilinear(z_a, z_b)
        return self.head(torch.cat([f_pair, s_bilinear], dim=-1))
