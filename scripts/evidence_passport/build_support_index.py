"""
Evidence Passport - Step 2: per-drug "training support" index.

How many documented pairs (real DDInter-labeled examples, not model
inferences) does each drug appear in? A drug with 400 documented pairs and a
drug with 2 documented pairs both get a severity prediction from Model 1,
but the second one's prediction rests on far less evidence about how that
drug behaves in combination - the Evidence Passport needs to say so.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "processed"
OUT_DIR = PROCESSED_DIR / "evidence_passport"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def main() -> None:
    df = pd.read_csv(PROCESSED_DIR / "polyguard_all_drugs_severity_pairs.csv")
    df = df[df["severity"].isin(["Minor", "Moderate", "Major"])].copy()

    counts: Counter[str] = Counter()
    for a, b in zip(df["drug_a"], df["drug_b"]):
        counts[normalize(a)] += 1
        counts[normalize(b)] += 1

    with open(OUT_DIR / "drug_support_counts.json", "w", encoding="utf-8") as f:
        json.dump(dict(counts), f)

    values = sorted(counts.values())
    n = len(values)
    print(f"Drugs indexed: {n}")
    print(f"Median documented-pair count: {values[n // 2]}")
    print(f"25th percentile: {values[int(n * 0.25)]}  75th percentile: {values[int(n * 0.75)]}")
    print(f"Min: {values[0]}  Max: {values[-1]}")

    # Tiers used by the Evidence Passport UI - thresholds chosen from the
    # distribution above (roughly quartile-based), not arbitrary.
    tiers = {"sparse_max": values[int(n * 0.25)], "limited_max": values[int(n * 0.60)]}
    with open(OUT_DIR / "support_tiers.json", "w", encoding="utf-8") as f:
        json.dump(tiers, f, indent=2)
    print(f"Support tiers: sparse <= {tiers['sparse_max']}, "
          f"limited <= {tiers['limited_max']}, well_represented > {tiers['limited_max']}")


if __name__ == "__main__":
    main()
