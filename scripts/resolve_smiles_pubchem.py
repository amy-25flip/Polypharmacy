from __future__ import annotations

import argparse
import csv
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

PUBCHEM_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/CanonicalSMILES/TXT"
)
REQUEST_DELAY_SECONDS = 0.35
MAX_RETRIES = 3
TIMEOUT_SECONDS = 15


def normalize_drug_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def load_unique_drug_names(csv_path: Path) -> list[str]:
    df = pd.read_csv(csv_path)
    names_a = df["drug_a"].dropna().map(str)
    names_b = df["drug_b"].dropna().map(str)
    all_names = pd.concat([names_a, names_b])
    # Keep one representative original spelling per normalized name.
    seen: dict[str, str] = {}
    for name in all_names:
        norm = normalize_drug_name(name)
        if norm and norm not in seen:
            seen[norm] = name.strip()
    return sorted(seen.items())


def fetch_smiles(name: str) -> str | None:
    url = PUBCHEM_URL.format(name=urllib.parse.quote(name, safe=""))
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PolyGuard-student-project/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                text = response.read().decode("utf-8").strip()
                return text.splitlines()[0] if text else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (503, 429) and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return None
        except (urllib.error.URLError, TimeoutError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def load_existing_cache(cache_path: Path) -> dict[str, str]:
    if not cache_path.exists():
        return {}
    df = pd.read_csv(cache_path)
    return {
        row["drug_name_norm"]: row["smiles"]
        for _, row in df.iterrows()
        if pd.notna(row.get("smiles")) and str(row.get("smiles")).strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve PolyGuard drug names to SMILES via PubChem.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(r"E:\Polypharmacy\processed\polyguard_all_drugs_severity_pairs.csv"),
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path(r"E:\Polypharmacy\processed\drug_name_smiles_cache.csv"),
    )
    args = parser.parse_args()

    unique_names = load_unique_drug_names(args.input_csv)
    print(f"Found {len(unique_names)} unique drug names to resolve.")

    existing = load_existing_cache(args.cache_path)
    print(f"{len(existing)} already resolved in cache; resuming from there.")

    fieldnames = ["drug_name_norm", "drug_name_original", "smiles"]
    write_header = not args.cache_path.exists()
    resolved_count = len(existing)
    attempted = 0

    with open(args.cache_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for norm_name, original_name in unique_names:
            if norm_name in existing:
                continue
            attempted += 1
            smiles = fetch_smiles(original_name)
            writer.writerow(
                {
                    "drug_name_norm": norm_name,
                    "drug_name_original": original_name,
                    "smiles": smiles or "",
                }
            )
            f.flush()
            if smiles:
                resolved_count += 1
            if attempted % 50 == 0:
                print(
                    f"Progress: {attempted} queried this run, "
                    f"{resolved_count}/{len(unique_names)} resolved total so far."
                )
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"Done. Resolved {resolved_count}/{len(unique_names)} drug names "
          f"({resolved_count / len(unique_names):.1%} coverage).")
    print(f"Cache written to {args.cache_path}")


if __name__ == "__main__":
    main()
