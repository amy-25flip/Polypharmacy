from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import DataLoader

from train_hoddi_deepsets import HoddiDataset, RANDOM_STATE, build_fingerprint_lookup, evaluate
from ablation_hoddi import AblatedModel

PREPARED_CSV = Path(r"E:\Polypharmacy\processed\hoddi_prepared.csv")
VOCABS_PATH = Path(r"E:\Polypharmacy\processed\hoddi_vocabs.json")
SMILES_PATH = Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv")
EPOCHS = 6
BATCH_SIZE = 512


def main() -> None:
    device = torch.device("cpu")
    torch.manual_seed(RANDOM_STATE)

    df = pd.read_csv(PREPARED_CSV, low_memory=False)
    with open(VOCABS_PATH, encoding="utf-8") as f:
        vocabs = json.load(f)

    print("Building fingerprint lookup...")
    fp_lookup = build_fingerprint_lookup(SMILES_PATH)

    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(df, groups=df["base_report_id"]))
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
    print(f"Train: {len(train_df)}  Test: {len(test_df)}")

    train_ds = HoddiDataset(train_df, fp_lookup, vocabs)
    test_ds = HoddiDataset(test_df, fp_lookup, vocabs)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    # Final headline model: drugs + context, NO AE code (SE_above_0.9 excluded - confirmed leakage).
    model = AblatedModel(vocabs, use_drugs=True, use_ae=False).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            logits = model(batch["fp"], batch["mask"], batch["cat_idx"], batch["se_idx"], batch["age"])
            loss = loss_fn(logits, batch["label"])
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch["label"])
        avg_loss = total_loss / len(train_ds)
        metrics = evaluate(model, test_loader, device)
        print(f"Epoch {epoch}/{EPOCHS} - train loss {avg_loss:.4f} - "
              f"test AUROC {metrics['auroc']:.4f}  AUPRC {metrics['auprc']:.4f}  F1 {metrics['f1']:.4f}")

    final = evaluate(model, test_loader, device)
    print("\n=== FINAL leakage-controlled HODDI DeepSets result (drugs + context, no AE code) ===")
    print(json.dumps(final, indent=2))

    torch.save(model.state_dict(), Path(r"E:\Polypharmacy\processed\hoddi_deepsets_final_model.pt"))
    print("Saved to E:\\Polypharmacy\\processed\\hoddi_deepsets_final_model.pt")


if __name__ == "__main__":
    main()
