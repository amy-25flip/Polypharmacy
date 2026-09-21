from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import DataLoader, Dataset

RDLogger.DisableLog("rdApp.*")

RANDOM_STATE = 42
MAX_SET_SIZE = 5
FP_BITS = 512
FP_RADIUS = 2
AGE_MISSING_SENTINEL = -1

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


CATEGORICAL_COLS = [
    "condition",
    "country",
    "gender",
    "quarter",
    "reporter_category",
    "reporter_description",
    "reporter_qualify_code",
]


class HoddiDataset(Dataset):
    def __init__(self, df: pd.DataFrame, fp_lookup: dict[str, np.ndarray], vocabs: dict[str, dict[str, int]]):
        self.df = df.reset_index(drop=True)
        self.fp_lookup = fp_lookup
        self.vocabs = vocabs
        age = self.df["age"].astype(float).values
        valid_age = age[age != AGE_MISSING_SENTINEL]
        self.age_mean = float(valid_age.mean()) if len(valid_age) else 0.0
        self.age_std = float(valid_age.std()) if len(valid_age) else 1.0

    def __len__(self) -> int:
        return len(self.df)

    def _vocab_idx(self, col: str, value) -> int:
        return self.vocabs[col].get(str(value), 0)

    def __getitem__(self, i: int):
        row = self.df.iloc[i]
        drug_ids = row["drug_ids"].split("|")

        fp_stack = np.zeros((MAX_SET_SIZE, FP_BITS), dtype=np.float32)
        mask = np.zeros((MAX_SET_SIZE,), dtype=np.float32)
        for j, drug_id in enumerate(drug_ids[:MAX_SET_SIZE]):
            fp = self.fp_lookup.get(drug_id)
            if fp is not None:
                fp_stack[j] = fp
                mask[j] = 1.0

        age_raw = float(row["age"])
        if age_raw == AGE_MISSING_SENTINEL:
            age_norm = 0.0
            age_missing = 1.0
        else:
            age_norm = (age_raw - self.age_mean) / (self.age_std + 1e-6)
            age_missing = 0.0

        cat_idx = np.array(
            [self._vocab_idx(col, row[col]) for col in CATEGORICAL_COLS], dtype=np.int64
        )
        se_idx = self._vocab_idx("SE_above_0.9", row["SE_above_0.9"])

        return {
            "fp": torch.from_numpy(fp_stack),
            "mask": torch.from_numpy(mask),
            "cat_idx": torch.from_numpy(cat_idx),
            "se_idx": torch.tensor(se_idx, dtype=torch.long),
            "age": torch.tensor([age_norm, age_missing], dtype=torch.float32),
            "label": torch.tensor(float(row["label"]), dtype=torch.float32),
            "set_size": torch.tensor(int(row["set_size"]), dtype=torch.long),
        }


class DeepSetsHoddiModel(nn.Module):
    def __init__(self, vocabs: dict[str, dict[str, int]]):
        super().__init__()
        self.drug_encoder = nn.Sequential(
            nn.Linear(FP_BITS, 256), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(256, 128), nn.ReLU(),
        )

        cat_emb_dim = 16
        self.cat_embeddings = nn.ModuleList(
            [nn.Embedding(len(vocabs[col]) + 1, cat_emb_dim, padding_idx=0) for col in CATEGORICAL_COLS]
        )
        self.se_embedding = nn.Embedding(len(vocabs["SE_above_0.9"]) + 1, 32, padding_idx=0)

        context_dim = cat_emb_dim * len(CATEGORICAL_COLS) + 32 + 2  # + age(norm, missing)
        set_dim = 128 * 2  # mean + max pooled

        self.classifier = nn.Sequential(
            nn.Linear(set_dim + context_dim, 256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 64), nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, fp, mask, cat_idx, se_idx, age):
        b, n, _ = fp.shape
        drug_vecs = self.drug_encoder(fp.view(b * n, -1)).view(b, n, -1)

        mask_exp = mask.unsqueeze(-1)
        masked = drug_vecs * mask_exp
        set_sum = masked.sum(dim=1)
        set_count = mask.sum(dim=1, keepdim=True).clamp(min=1.0)
        set_mean = set_sum / set_count
        set_max = torch.where(mask_exp.bool(), drug_vecs, torch.full_like(drug_vecs, -1e9)).max(dim=1).values
        set_repr = torch.cat([set_mean, set_max], dim=-1)

        cat_embs = [emb(cat_idx[:, i]) for i, emb in enumerate(self.cat_embeddings)]
        se_emb = self.se_embedding(se_idx)
        context_repr = torch.cat([*cat_embs, se_emb, age], dim=-1)

        combined = torch.cat([set_repr, context_repr], dim=-1)
        return self.classifier(combined).squeeze(-1)


def evaluate(model, loader, device) -> dict:
    model.eval()
    all_logits, all_labels, all_set_sizes = [], [], []
    with torch.no_grad():
        for batch in loader:
            logits = model(
                batch["fp"].to(device), batch["mask"].to(device),
                batch["cat_idx"].to(device), batch["se_idx"].to(device), batch["age"].to(device),
            )
            all_logits.append(logits.cpu().numpy())
            all_labels.append(batch["label"].numpy())
            all_set_sizes.append(batch["set_size"].numpy())

    logits = np.concatenate(all_logits)
    labels = np.concatenate(all_labels)
    set_sizes = np.concatenate(all_set_sizes)
    probs = 1 / (1 + np.exp(-logits))
    preds = (probs >= 0.5).astype(int)

    metrics = {
        "auroc": roc_auc_score(labels, probs),
        "auprc": average_precision_score(labels, probs),
        "f1": f1_score(labels, preds),
        "n": len(labels),
    }
    for size in sorted(set(set_sizes.tolist())):
        m = set_sizes == size
        if m.sum() > 10 and len(set(labels[m].tolist())) > 1:
            metrics[f"auroc_set{size}"] = roc_auc_score(labels[m], probs[m])
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the HODDI DeepSets higher-order interaction model.")
    parser.add_argument("--prepared-csv", type=Path, default=Path(r"E:\Polypharmacy\processed\hoddi_prepared.csv"))
    parser.add_argument("--vocabs-path", type=Path, default=Path(r"E:\Polypharmacy\processed\hoddi_vocabs.json"))
    parser.add_argument("--smiles-path", type=Path, default=Path(r"E:\Polypharmacy\Datasets\DrugBankID2SMILES.csv"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()

    torch.manual_seed(RANDOM_STATE)
    device = torch.device("cpu")

    df = pd.read_csv(args.prepared_csv)
    with open(args.vocabs_path, encoding="utf-8") as f:
        vocabs = json.load(f)

    print("Building fingerprint lookup...")
    fp_lookup = build_fingerprint_lookup(args.smiles_path)
    print(f"{len(fp_lookup)} drug fingerprints ready.")

    gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(df, groups=df["base_report_id"]))
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]
    print(f"Train: {len(train_df)} rows, Test: {len(test_df)} rows "
          f"(grouped by base_report_id, no overlap).")
    print(f"Train label balance: {train_df['label'].value_counts().to_dict()}")
    print(f"Test label balance: {test_df['label'].value_counts().to_dict()}")

    train_ds = HoddiDataset(train_df, fp_lookup, vocabs)
    test_ds = HoddiDataset(test_df, fp_lookup, vocabs)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = DeepSetsHoddiModel(vocabs).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            logits = model(
                batch["fp"].to(device), batch["mask"].to(device),
                batch["cat_idx"].to(device), batch["se_idx"].to(device), batch["age"].to(device),
            )
            loss = loss_fn(logits, batch["label"].to(device))
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(batch["label"])
        avg_loss = total_loss / len(train_ds)

        test_metrics = evaluate(model, test_loader, device)
        print(f"Epoch {epoch}/{args.epochs} - train loss {avg_loss:.4f} - "
              f"test AUROC {test_metrics['auroc']:.4f}  AUPRC {test_metrics['auprc']:.4f}  F1 {test_metrics['f1']:.4f}")

    final_metrics = evaluate(model, test_loader, device)
    print("\n=== Final HODDI DeepSets results (group-aware split, no PRR/CI/p-value leakage features) ===")
    print(json.dumps(final_metrics, indent=2))

    torch.save(model.state_dict(), Path(r"E:\Polypharmacy\processed\hoddi_deepsets_model.pt"))
    print("Model saved to E:\\Polypharmacy\\processed\\hoddi_deepsets_model.pt")


if __name__ == "__main__":
    main()
