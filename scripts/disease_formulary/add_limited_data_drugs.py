"""Add drugs the interaction database does not cover to the drug list, marked "limited data".

Run from any directory: python scripts/disease_formulary/add_limited_data_drugs.py
Reads the "limited_data" lists in new_conditions.json and updates processed/drug_vocabulary.json (new
names) and processed/drug_aliases.json ("limited_data" notes). Pairs with these drugs are reported as
"Not checked" instead of being guessed. Safe to re-run.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("new_conditions.json")
VOCABULARY = ROOT / "processed" / "drug_vocabulary.json"
ALIASES = ROOT / "processed" / "drug_aliases.json"

NOTES = {
    "topical": ("is applied to the skin and has no interaction records in the reference database. Interactions through "
                "the skin are unlikely, but this pair was not checked."),
    "systemic": ("has no interaction records in the reference database, so pairs with it were not checked. "
                 "Check it against the other medicines separately."),
}


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    wanted, custom_notes = source["limited_data"], source.get("limited_notes", {})
    vocabulary = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    known = set(vocabulary)
    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))
    limited = aliases.setdefault("limited_data", {})
    added = []
    for kind, names in wanted.items():
        for name in names:
            if name not in known:
                known.add(name)
                added.append(name)
            limited[name] = {"kind": kind, "note": custom_notes.get(name, NOTES[kind])}
    # The vocabulary file is a sorted JSON list with CRLF line endings and a two-space indent.
    VOCABULARY.write_text(json.dumps(sorted(known), indent=2, ensure_ascii=False).replace("\n", "\r\n"),
                          encoding="utf-8", newline="")
    ALIASES.write_text(json.dumps(aliases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Added {len(added)} names to the vocabulary ({len(known)} total); {len(limited)} limited-data drugs")


if __name__ == "__main__":
    main()
