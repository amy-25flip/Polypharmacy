"""Find medicines whose FDA label lists a condition among its approved uses (reverse indication search).

Run from any directory: python scripts/disease_formulary/fda_indications.py
For every condition in curated_formulary.json that has "fda_phrases", ask openFDA which drug labels
mention each phrase in their "indications and usage" section (one request per phrase) and cache the
answers in Datasets/openfda_indications/ (not tracked). build_disease_formulary.py then turns the
answers into medicine suggestions that carry the source "fda-label:indicated".

openFDA allows 1,000 unauthenticated requests a day; one request per phrase is far below that.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONDITION_FILES = [Path(__file__).with_name("curated_formulary.json"), Path(__file__).with_name("new_conditions.json")]
CACHE = ROOT / "Datasets" / "openfda_indications"

SALT_WORDS = {
    "hydrochloride", "hcl", "phosphate", "sodium", "potassium", "nitrate", "propionate", "dipropionate",
    "acetate", "sulfate", "sulphate", "succinate", "tartrate", "maleate", "mesylate", "besylate", "fumarate",
    "citrate", "bromide", "chloride", "valerate", "furoate", "benzoate", "hydrobromide", "monohydrate",
    "dihydrate", "anhydrous", "calcium", "magnesium", "olamine", "usp", "bitartrate", "tosylate",
    "hyclate", "monohydrochloride", "dihydrochloride", "pamoate", "lactate", "carbonate", "oxide",
}
FORM_WORDS = {"cream", "gel", "ointment", "lotion", "solution", "spray", "powder", "tablets", "tablet",
              "capsules", "capsule", "foam", "shampoo", "liquid", "topical", "oral", "injection", "ophthalmic",
              "suspension", "kit", "wash", "pads", "pad", "cleanser", "emulsion", "and", "w/w", "w/v"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def fetch_phrase(phrase: str, limit: int = 100) -> list[dict]:
    query = f'indications_and_usage:"{phrase}"'
    url = ("https://api.fda.gov/drug/label.json?search=" + urllib.parse.quote(query, safe=':"+')
           + f"&count=openfda.generic_name.exact&limit={limit}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                return json.load(response)["results"]
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return []
            if error.code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5)
    raise SystemExit("openFDA unreachable")


def strip_name(name: str) -> str:
    words = re.split(r"\s+", name.lower().strip())
    kept = [w for w in words if w not in SALT_WORDS and w not in FORM_WORDS and not re.fullmatch(r"[\d.]+", w)]
    return " ".join(kept)


def build_lookup(vocabulary: list[str], synonyms: dict[str, list[str]] | None = None,
                 route: str | None = None) -> dict[str, str]:
    """Names a label may use -> vocabulary name: exact, salt-stripped (Clobetasol propionate), and synonyms.

    With ``route`` (for example "topical"), a drug that has a "(topical)" entry resolves to that entry
    instead of the systemic one, so a haemorrhoid cream is not checked as if it were a tablet.
    """
    lookup: dict[str, str] = {}
    if route:
        for name in vocabulary:
            if name.endswith(f"({route})"):
                base = re.sub(r"\s*\(.*?\)", "", name).strip()
                lookup.setdefault(base.lower(), name)
                lookup.setdefault(strip_name(base), name)
    for name in vocabulary:
        if "(" not in name:
            lookup.setdefault(name.lower(), name)
            lookup.setdefault(strip_name(name), name)
    for name in vocabulary:  # "Clobetasol (topical)" answers to a label that says CLOBETASOL
        if "(" in name:
            base = re.sub(r"\s*\(.*?\)", "", name).strip()
            lookup.setdefault(base.lower(), name)
            lookup.setdefault(strip_name(base), name)
    for synonym, targets in (synonyms or {}).items():
        if len(targets) == 1:
            lookup.setdefault(synonym.lower(), targets[0])
    return lookup


def vocabulary_name(term: str, vocab_by_norm: dict[str, str]) -> str | None:
    """Map an openFDA generic name ("CLINDAMYCIN PHOSPHATE") to a vocabulary drug, or None.

    Combination products are skipped: their label says nothing reliable about one component.
    """
    lowered = term.lower()
    if any(mark in lowered for mark in (",", "/", " with ", " kit", "%")):
        return None
    words = [w for w in re.split(r"\s+", lowered) if w]
    if "and" in words:
        return None
    words = [re.sub(r"-[a-z]{4}$", "", w) for w in words]  # biosimilar suffix: adalimumab-ryvk
    kept = [w for w in words if w not in SALT_WORDS and w not in FORM_WORDS and not re.fullmatch(r"[\d.]+", w)]
    for candidate in (" ".join(kept), " ".join(words)):
        if candidate in vocab_by_norm:
            return vocab_by_norm[candidate]
    return None


def candidates(phrases: list[str], vocab_by_norm: dict[str, str], minimum_labels: int = 2) -> dict[str, int]:
    """Vocabulary drug -> number of labels naming one of the phrases (cached answers only)."""
    totals: dict[str, int] = {}
    for phrase in phrases:
        path = CACHE / f"{slug(phrase)}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            drug = vocabulary_name(row["term"], vocab_by_norm)
            if drug:
                totals[drug] = totals.get(drug, 0) + row["count"]
    return {drug: count for drug, count in totals.items() if count >= minimum_labels}


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    phrases = sorted({p for path in CONDITION_FILES if path.exists()
                      for d in json.loads(path.read_text(encoding="utf-8"))["diseases"]
                      for p in d.get("fda_phrases", [])})
    todo = [p for p in phrases if not (CACHE / f"{slug(p)}.json").exists()]
    print(f"{len(phrases)} phrases, {len(todo)} to fetch")
    for index, phrase in enumerate(todo, start=1):
        (CACHE / f"{slug(phrase)}.json").write_text(json.dumps(fetch_phrase(phrase)), encoding="utf-8")
        time.sleep(0.4)
        if index % 20 == 0:
            print(f"  {index}/{len(todo)}")
    print(f"Done. Cache: {CACHE}")


if __name__ == "__main__":
    main()
