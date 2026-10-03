"""Turn the cached FDA label text into two small files the app and the review workbook use.

Run from any directory: python scripts/fda_labels/build_label_evidence.py

* processed/label_interactions.json: for each pair of medicines where one drug's FDA label names
  the other in its drug-interactions section, the sentence that does so (pair-specific evidence,
  and the adverse effects that sentence names).
* processed/label_indications.json: the indications text of each drug's label, used to check the
  disease -> medicine lists.

Source: openFDA drug labels (public domain). Run fetch_labels.py first.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "Datasets" / "openfda_labels"
INTERACTIONS_OUT = ROOT / "processed" / "label_interactions.json"
INDICATIONS_OUT = ROOT / "processed" / "label_indications.json"

MAX_SNIPPET = 340
MAX_PER_DIRECTION = 2
MAX_LIST_SNIPPET = 220

# Effects a sentence can name. Order matters only for display.
EFFECTS = [
    (r"bleed|hemorrhag|haemorrhag|anticoagulant effect|INR", "Bleeding"),
    (r"hypoglyc", "Low blood sugar"),
    (r"hyperglyc", "High blood sugar"),
    (r"hyperkal", "High potassium"),
    (r"hypokal", "Low potassium"),
    (r"hyponatr", "Low sodium"),
    (r"QT[ -]?(interval )?prolong|torsade", "QT prolongation"),
    (r"serotonin syndrome", "Serotonin syndrome"),
    (r"rhabdomyolysis|myopathy|myotoxicity", "Muscle damage"),
    (r"nephrotox|renal (impairment|failure|toxicity)|kidney (injury|damage|failure)", "Kidney injury"),
    (r"hepatotox|liver (injury|damage|toxicity)|hepatic (injury|toxicity)", "Liver injury"),
    (r"CNS depress|sedation|somnolence|drowsiness", "Sedation"),
    (r"respiratory depression", "Respiratory depression"),
    (r"hypotension|blood pressure lowering|lower blood pressure", "Low blood pressure"),
    (r"hypertensi|raise blood pressure|increase blood pressure", "High blood pressure"),
    (r"bradycardia|heart block|AV block", "Slow heart rate"),
    (r"lactic acidosis", "Lactic acidosis"),
    (r"seizure|convuls", "Seizures"),
    (r"ototox", "Hearing damage"),
    (r"tendon", "Tendon problems"),
    (r"ulcer|gastrointestinal (bleeding|irritation)", "Stomach ulcer"),
    (r"angioedema", "Angioedema"),
    (r"neutropeni|myelosuppress|bone marrow suppress|agranulocytosis", "Low blood counts"),
    (r"hyperthermia|hypothermia", "Temperature disturbance"),
    (r"(increase|increased|elevat|higher|raise|raised)[^.]{0,60}(concentration|level|exposure|AUC)", "Higher drug levels"),
    (r"(decrease|decreased|reduc|lower|lowered)[^.]{0,60}(concentration|level|exposure|AUC)", "Lower drug levels"),
    (r"(reduced|decreased|diminished|loss of)[^.]{0,40}(efficacy|effectiveness|effect\b)", "Reduced effect"),
    (r"toxicity", "Toxicity"),
]
EFFECT_PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in EFFECTS]


def norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


def name_patterns(vocabulary: list[str], synonyms: dict[str, list[str]]) -> tuple[re.Pattern, dict[str, str]]:
    """One regex for every drug name (and synonym) with its canonical vocabulary name."""
    lookup: dict[str, str] = {}
    for name in vocabulary:
        base = re.sub(r"\s*\(.*?\)", "", name).strip()
        if len(base) >= 4:
            lookup.setdefault(norm(base), name if "(" not in name else base)
    for synonym, targets in synonyms.items():
        if len(synonym) >= 4 and len(targets) == 1:
            lookup.setdefault(norm(synonym), targets[0])
    names = sorted(lookup, key=len, reverse=True)
    pattern = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z])", re.IGNORECASE)
    return pattern, lookup


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"^\s*\d+(\.\d+)*\s+(DRUG INTERACTIONS|Drug Interactions)\s*", "", text)


def snippet_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start))
    left = 0 if left < 0 else left + 2
    right_candidates = [i for i in (text.find(". ", end), text.find("; ", end)) if i >= 0]
    right = min(right_candidates) + 1 if right_candidates else len(text)
    sentence = text[left:right].strip()
    limit = MAX_LIST_SNIPPET if is_list(sentence) else MAX_SNIPPET
    if len(sentence) > limit:
        mid = start - left
        lo = max(0, mid - limit // 2)
        # Start and end on word boundaries so the quote never begins or ends mid-word.
        window = sentence[lo: lo + limit]
        if lo:
            window = window.split(" ", 1)[-1]
        if lo + limit < len(sentence):
            window = window.rsplit(" ", 1)[0]
        sentence = ("…" if lo else "") + window.strip() + "…"
    return sentence


def is_list(sentence: str) -> bool:
    """Table rows and long enumerations of drug names say little about the pair."""
    return sentence.startswith("Table") or sentence.count(",") > 7


def effects_in(sentence: str) -> list[str]:
    return [label for pattern, label in EFFECT_PATTERNS if pattern.search(sentence)][:4]


def main() -> None:
    vocabulary = json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8"))
    aliases = json.loads((ROOT / "processed" / "drug_aliases.json").read_text(encoding="utf-8"))
    pattern, lookup = name_patterns(vocabulary, aliases["synonyms"])

    pairs: dict[str, list[dict]] = defaultdict(list)
    indications: dict[str, dict] = {}
    labels = drugs_with_interactions = 0
    for path in sorted(CACHE.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("found"):
            continue
        labels += 1
        drug = record["drug"]
        if record.get("indications_and_usage"):
            indications[drug] = {"text": clean(record["indications_and_usage"])[:900],
                                 "label": (record.get("generic_name") or [drug])[0]}
        text = clean(record.get("drug_interactions", ""))
        if not text:
            continue
        drugs_with_interactions += 1
        seen_per_other: dict[str, int] = defaultdict(int)
        for match in pattern.finditer(text):
            other = lookup[norm(match.group(1))]
            if norm(other) == norm(drug):
                continue
            if seen_per_other[other] >= MAX_PER_DIRECTION:
                continue
            sentence = snippet_around(text, match.start(), match.end())
            if len(sentence) < 25:
                continue
            seen_per_other[other] += 1
            key = "|".join(sorted((norm(drug), norm(other))))
            entry = {"from": drug, "text": sentence, "effects": effects_in(sentence)}
            if is_list(sentence):
                entry["list"] = True
            pairs[key].append(entry)

    INTERACTIONS_OUT.write_text(json.dumps({"source": "openFDA drug labels (public domain)", "pairs": pairs},
                                           ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    INDICATIONS_OUT.write_text(json.dumps(indications, ensure_ascii=False, separators=(",", ":")) + "\n",
                               encoding="utf-8")
    with_effects = sum(any(e["effects"] for e in entries) for entries in pairs.values())
    print(f"{labels} labels, {drugs_with_interactions} with an interactions section; "
          f"{len(pairs)} pairs named in a label ({with_effects} naming an effect); "
          f"{len(indications)} indication texts")
    print(f"Wrote {INTERACTIONS_OUT} ({INTERACTIONS_OUT.stat().st_size / 1e6:.1f} MB) and {INDICATIONS_OUT}")


if __name__ == "__main__":
    main()
