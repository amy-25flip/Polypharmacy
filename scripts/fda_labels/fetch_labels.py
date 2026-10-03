"""Download FDA drug-label text (openFDA) for the medicines doctors are most likely to enter.

Run from any directory: python scripts/fda_labels/fetch_labels.py
Cache: Datasets/openfda_labels/<slug>.json (not tracked). Re-running skips cached drugs.

openFDA allows 1,000 unauthenticated requests a day, so the scope is limited to medicines on
the disease lists, the Indian brand-name index, the borrowed-record relatives and a few common
drugs (about 800). Pass --all to try every vocabulary name (needs an API key in OPENFDA_API_KEY).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "Datasets" / "openfda_labels"
FIELDS = ("drug_interactions", "indications_and_usage", "contraindications", "geriatric_use")
MAX_CHARS = {"drug_interactions": 60_000, "indications_and_usage": 4_000,
             "contraindications": 3_000, "geriatric_use": 2_000}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def scope(everything: bool) -> list[str]:
    vocabulary = json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8"))
    if everything:
        return [name for name in vocabulary if "(" not in name]
    names: set[str] = set()
    formulary = json.loads((ROOT / "processed" / "disease_formulary.json").read_text(encoding="utf-8"))
    names.update(m["name"] for d in formulary["diseases"] for m in d["medicines"])
    for generics in json.loads((ROOT / "processed" / "indian_brand_names.json").read_text(encoding="utf-8")).values():
        names.update(generics)
    aliases = json.loads((ROOT / "processed" / "drug_aliases.json").read_text(encoding="utf-8"))
    names.update(info["proxy"] for info in aliases["estimated"].values())
    names.update(target for targets in aliases["synonyms"].values() for target in targets)
    names.update(["Warfarin", "Amiodarone", "Metformin", "Amlodipine", "Losartan", "Atorvastatin", "Clopidogrel",
                  "Omeprazole", "Ibuprofen", "Levothyroxine", "Sertraline", "Digoxin", "Spironolactone",
                  "Apixaban", "Nitrofurantoin", "Acetylsalicylic acid", "Acetaminophen"])
    known = set(vocabulary)
    return sorted(n for n in names if n in known and "(" not in n)


def query(search: str, key: str | None) -> dict | None:
    params = {"search": search, "limit": "5"}
    if key:
        params["api_key"] = key
    url = "https://api.fda.gov/drug/label.json?" + urllib.parse.urlencode(params, safe='":+_()')
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5)
    raise SystemExit("openFDA unreachable")


def pick(results: list[dict], name: str) -> dict | None:
    """Prefer a single-ingredient label for exactly this drug that has an interactions section."""
    target = name.lower()
    best = None
    for label in results:
        generic = [g.lower() for g in label.get("openfda", {}).get("generic_name", [])]
        score = (target in generic, len(generic) == 1, bool(label.get("drug_interactions")),
                 -len(generic))
        if best is None or score > best[0]:
            best = (score, label)
    return best[1] if best else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0,
                        help="start this far into the list (wraps), so several runs can share the work")
    args = parser.parse_args()
    key = os.environ.get("OPENFDA_API_KEY")
    CACHE.mkdir(parents=True, exist_ok=True)
    names = scope(args.all)
    if args.limit:
        names = names[: args.limit]
    todo = [n for n in names if not (CACHE / f"{slug(n)}.json").exists()]
    if todo and args.offset:
        shift = args.offset % len(todo)
        todo = todo[shift:] + todo[:shift]
    print(f"{len(names)} drugs in scope, {len(todo)} to fetch")
    found = 0
    for index, name in enumerate(todo, start=1):
        if (CACHE / f"{slug(name)}.json").exists():  # another run got there first
            continue
        record = {"drug": name, "found": False}
        for search in (f'openfda.generic_name:"{name}"+AND+_exists_:drug_interactions',
                       f'openfda.substance_name:"{name}"+AND+_exists_:drug_interactions',
                       f'openfda.generic_name:"{name}"'):
            data = query(search, key)
            time.sleep(0.3)
            label = pick(data["results"], name) if data else None
            if label:
                record = {"drug": name, "found": True, "set_id": label.get("set_id"),
                          "effective_time": label.get("effective_time"),
                          "generic_name": label.get("openfda", {}).get("generic_name", []),
                          "brand_name": label.get("openfda", {}).get("brand_name", [])[:3]}
                for field in FIELDS:
                    text = " ".join(label.get(field, []))
                    record[field] = text[: MAX_CHARS[field]]
                found += 1
                break
        (CACHE / f"{slug(name)}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        if index % 50 == 0:
            print(f"  {index}/{len(todo)} fetched, {found} with a label")
    print(f"Done: {found}/{len(todo)} had a label. Cache: {CACHE}")


if __name__ == "__main__":
    main()
