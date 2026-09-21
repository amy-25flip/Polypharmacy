from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import DataLoader

from train_hoddi_deepsets import (
    CATEGORICAL_COLS,
    HoddiDataset,
    RANDOM_STATE,
    build_fingerprint_lookup,
    evaluate,
)


class AblatedModel(nn.Module):
    """Same as DeepSetsHoddiModel but can zero out the drug-set branch or the AE branch."""

    def __init__(self, vocabs, use_drugs: bool, use_ae: bool):
        super().__init__()
        self.use_drugs = use_drugs
        self.use_ae = use_ae

        self.drug_encoder = nn.Sequential(
            nn.Linear(512, 256), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(256, 128), nn.ReLU(),
        )
        cat_emb_dim = 16
        self.cat_embeddings = nn.ModuleList(
            [nn.Embedding(len(vocabs[col]) + 1, cat_emb_dim, padding_idx=0) for col in CATEGORICAL_COLS]
        )
        self.se_embedding = nn.Embedding(len(vocabs["SE_above_0.9"]) + 1, 32, padding_idx=0)

        context_dim = cat_emb_dim * len(CATEGORICAL_COLS) + 32 + 2
        set_dim = 128 * 2

        self.classifier = nn.Sequential(
            nn.Linear(set_dim + context_dim, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, fp, mask, cat_idx, se_idx, age):
        if self.use_drugs:
            b, n, _ = fp.shape
            drug_vecs = self.drug_encoder(fp.view(b * n, -1)).view(b, n, -1)
            mask_exp = mask.unsqueeze(-1)
            masked = drug_vecs * mask_exp
            set_mean = masked.sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp(min=1.0)
            set_max = torch.where(mask_exp.bool(), drug_vecs, torch.full_like(drug_vecs, -1e9)).max(dim=1).values
            set_repr = torch.cat([set_mean, set_max], dim=-1)
        else:
            b = fp.shape[0]
            set_repr = torch.zeros(b, 256, device=fp.device)

        cat_embs = [emb(cat_idx[:, i]) for i, emb in enumerate(self.cat_embeddings)]
        if self.use_ae:
            se_emb = self.se_embedding(se_idx)
        else:
            se_emb = torch.zeros(fp.shape[0], 32, device=fp.device)
        context_repr = torch.cat([*cat_embs, se_emb, age], dim=-1)

        combined = torch.cat([set_repr, context_repr], dim=-1)
        return self.classifier(combined).squeeze(-1)


def run_ablation(name: str, use_drugs: bool, use_ae: bool, train_ds, test_ds, vocabs, epochs: int, batch_size: int):
    device = torch.device("cpu")
    torch.manual_seed(RANDOM_STATE)
    model = AblatedModel(vocabs, use_drugs=use_drugs, use_ae=use_ae).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    for epoch in range(1, epochs + 1):
        model.train()
        for batch in train_loader:
            optimizer.zero_grad()
            logits = model(batch["fp"], batch["mask"], batch["cat_idx"], batch["se_idx"], batch["age"])
            loss = loss_fn(logits, batch["label"])
            loss.backward()
            optimizer.step()

    metrics = evaluate(model, test_loader, device)
    print(f"[{name}] AUROC {metrics['auroc']:.4f}  AUPRC {metrics['auprc']:.4f}  F1 {metrics['f1']:.4f}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation checks for the HODDI DeepSets model.")
    parser.add_argument("--prepared-csv", type=Path, default=Path(r"E:\Polypharmacy\processed\hoddi_prepared.csv"))
    parser.add_argument("--vocabs-path", type=Path, default=Path(r"E:\Polypharmacy\processed\hoddi_vocabs.json"))
    parser.add_argument("--smiles-path", type=Path, default=Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()

    df = pd.read_csv(args.prepared_csv, low_memory=False)
    with open(args.vocabs_path, encoding="utf-8") as f:
        vocabs = json.load(f)

    print("Building fingerprint lookup...")
    fp_lookup = build_fingerprint_lookup(args.smiles_path)

    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(df, groups=df["base_report_id"]))
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]

    train_ds = HoddiDataset(train_df, fp_lookup, vocabs)
    test_ds = HoddiDataset(test_df, fp_lookup, vocabs)

    print("\n=== Ablation results ===")
    run_ablation("drugs_only (no AE)", use_drugs=True, use_ae=False, train_ds=train_ds, test_ds=test_ds,
                 vocabs=vocabs, epochs=args.epochs, batch_size=args.batch_size)
    run_ablation("ae_and_context_only (NO drug fingerprints)", use_drugs=False, use_ae=True, train_ds=train_ds, test_ds=test_ds,
                 vocabs=vocabs, epochs=args.epochs, batch_size=args.batch_size)
    run_ablation("context_only (no drugs, no AE)", use_drugs=False, use_ae=False, train_ds=train_ds, test_ds=test_ds,
                 vocabs=vocabs, epochs=args.epochs, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
