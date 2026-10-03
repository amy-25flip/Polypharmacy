"""Alternative drug names, and borrowed records for drugs that have none of their own.

Two different things live in processed/drug_aliases.json:

* ``synonyms``: another name for a drug that is already in the vocabulary (aspirin is
  Acetylsalicylic acid). These only help search and are exact.
* ``estimated``: drugs the interaction database has no records for (gliclazide). Checks
  borrow the records of a close relative (glimepiride) and are always labelled as
  estimates, never as documented results.
"""
from __future__ import annotations

import json
from pathlib import Path


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


class DrugAliases:
    def __init__(self, path: Path, vocabulary: list[str]):
        data = json.loads(path.read_text(encoding="utf-8"))
        known = set(vocabulary)
        self.synonyms: dict[str, list[str]] = {
            _norm(name): targets for name, targets in data["synonyms"].items()
            if all(target in known for target in targets)
        }
        self._estimated: dict[str, dict] = {
            _norm(name): {"drug": name, "proxy": info["proxy"], "reason": info["reason"]}
            for name, info in data["estimated"].items()
            if name in known and info["proxy"] in known
        }

    def lookup_synonyms(self, query: str) -> list[tuple[str, list[str]]]:
        """Synonyms whose name starts with, or contains, the typed text (exact hit first)."""
        q = _norm(query)
        if not q:
            return []
        if q in self.synonyms:
            return [(q, self.synonyms[q])]
        return [(name, targets) for name, targets in self.synonyms.items() if name.startswith(q)]

    def estimate(self, drug: str) -> dict | None:
        """``{"drug", "proxy", "reason"}`` if this drug is checked through a relative."""
        return self._estimated.get(_norm(drug))

    def effective(self, drug: str) -> str:
        """The drug whose records are used for checking (the drug itself unless estimated)."""
        info = self.estimate(drug)
        return info["proxy"] if info else drug

    def notes(self, *drugs: str) -> list[dict]:
        return [{"drug": info["drug"], "proxy": info["proxy"], "reason": info["reason"]}
                for info in (self.estimate(d) for d in drugs) if info]
