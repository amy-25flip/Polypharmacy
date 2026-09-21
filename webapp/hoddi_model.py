from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator

RDLogger.DisableLog("rdApp.*")

FP_BITS = 512
FP_RADIUS = 2
MAX_SET_SIZE = 5
AGE_MISSING_SENTINEL = -1

HODDI_CATEGORICAL_COLS = [
    "condition",
    "country",
    "gender",
    "quarter",
    "reporter_category",
    "reporter_description",
    "reporter_qualify_code",
]

_fp_generator = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_BITS)


def smiles_to_bits(smiles: str) -> np.ndarray | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = _fp_generator.GetFingerprint(mol)
    arr = np.zeros((FP_BITS,), dtype=np.float32)
    for bit in fp.GetOnBits():
        arr[bit] = 1.0
    return arr


def build_fingerprint_lookup(smiles_path: Path) -> dict[str, np.ndarray]:
    df = pd.read_csv(smiles_path)
    lookup: dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        smiles = row.get("smiles")
        if pd.isna(smiles) or not str(smiles).strip():
            continue
        bits = smiles_to_bits(str(smiles))
        if bits is not None:
            lookup[row["drugbank_id"]] = bits
    return lookup


class HoddiInferenceModel(nn.Module):
    """Same architecture as the trained 'drugs + context, no AE' model (ablation_hoddi.AblatedModel
    with use_drugs=True, use_ae=False) - kept structurally identical so the saved state_dict loads."""

    def __init__(self, vocabs: dict[str, dict[str, int]]):
        super().__init__()
        self.vocabs = vocabs

        self.drug_encoder = nn.Sequential(
            nn.Linear(FP_BITS, 256), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(256, 128), nn.ReLU(),
        )
        cat_emb_dim = 16
        self.cat_embeddings = nn.ModuleList(
            [nn.Embedding(len(vocabs[col]) + 1, cat_emb_dim, padding_idx=0) for col in HODDI_CATEGORICAL_COLS]
        )
        self.se_embedding = nn.Embedding(len(vocabs["SE_above_0.9"]) + 1, 32, padding_idx=0)  # unused (use_ae=False)

        context_dim = cat_emb_dim * len(HODDI_CATEGORICAL_COLS) + 32 + 2
        set_dim = 128 * 2
        self.classifier = nn.Sequential(
            nn.Linear(set_dim + context_dim, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, fp, mask, cat_idx, age):
        b, n, _ = fp.shape
        drug_vecs = self.drug_encoder(fp.view(b * n, -1)).view(b, n, -1)
        mask_exp = mask.unsqueeze(-1)
        masked = drug_vecs * mask_exp
        set_mean = masked.sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp(min=1.0)
        set_max = torch.where(mask_exp.bool(), drug_vecs, torch.full_like(drug_vecs, -1e9)).max(dim=1).values
        set_repr = torch.cat([set_mean, set_max], dim=-1)

        cat_embs = [emb(cat_idx[:, i]) for i, emb in enumerate(self.cat_embeddings)]
        se_emb = torch.zeros(b, 32)  # AE branch unused for this model
        context_repr = torch.cat([*cat_embs, se_emb, age], dim=-1)

        combined = torch.cat([set_repr, context_repr], dim=-1)
        return self.classifier(combined).squeeze(-1)

    @torch.no_grad()
    def predict_proba(self, drugbank_ids: list[str], fp_lookup: dict[str, np.ndarray]) -> float:
        """No real patient context is collected in this UI yet, so context fields use the
        'unknown' embedding slot (index 0) and age uses the missing-value sentinel - the model
        was trained to handle this exact case."""
        fp_stack = np.zeros((MAX_SET_SIZE, FP_BITS), dtype=np.float32)
        mask = np.zeros((MAX_SET_SIZE,), dtype=np.float32)
        for j, drug_id in enumerate(drugbank_ids[:MAX_SET_SIZE]):
            fp = fp_lookup.get(drug_id)
            if fp is not None:
                fp_stack[j] = fp
                mask[j] = 1.0

        cat_idx = np.zeros((len(HODDI_CATEGORICAL_COLS),), dtype=np.int64)  # all "unknown"
        age = np.array([0.0, 1.0], dtype=np.float32)  # normalized age = 0, missing flag = 1

        fp_t = torch.from_numpy(fp_stack).unsqueeze(0)
        mask_t = torch.from_numpy(mask).unsqueeze(0)
        cat_t = torch.from_numpy(cat_idx).unsqueeze(0)
        age_t = torch.from_numpy(age).unsqueeze(0)

        logit = self.forward(fp_t, mask_t, cat_t, age_t)
        return float(torch.sigmoid(logit).item())
