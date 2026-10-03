"""Write processed/documented_severity.json: the documented severity of every known pair.

Run from any directory: python scripts/build_documented_severity.py
The app reads this file so a documented pair is always shown with its documented severity
instead of the model's guess. Keys match processed/documented_pairs.json.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "processed" / "polyguard_all_drugs_severity_pairs.csv"
OUTPUT = ROOT / "processed" / "documented_severity.json"


def main() -> None:
    by_severity: dict[str, list[str]] = defaultdict(list)
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = "|".join(sorted((row["pair_drug_1_norm"], row["pair_drug_2_norm"])))
            by_severity[row["severity"]].append(key)
    for keys in by_severity.values():
        keys.sort()
    documented = set(json.loads((ROOT / "processed" / "documented_pairs.json").read_text(encoding="utf-8")))
    flat = [key for keys in by_severity.values() for key in keys]
    if set(flat) != documented or len(flat) != len(documented):
        raise SystemExit("documented_severity does not match documented_pairs.json")
    OUTPUT.write_text(json.dumps(by_severity, separators=(",", ":")) + "\n", encoding="utf-8")
    print("PASS:", {severity: len(keys) for severity, keys in by_severity.items()}, "->", OUTPUT)


if __name__ == "__main__":
    main()
