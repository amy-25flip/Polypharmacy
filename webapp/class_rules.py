"""Well-established drug-class interactions that must not be shown as "No reaction" or a weak model guess.

processed/class_interaction_rules.json (built by scripts/class_rules/build_rules.py) lists pairs of drug
classes with a minimum severity and the reason. A rule only raises the severity of a pair that has no
documented record; a documented severity is never changed. These are decision-support floors taken from
FDA label warnings; a pharmacist has not yet reviewed them.
"""
from __future__ import annotations

import json
from pathlib import Path


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


class ClassRules:
    def __init__(self, path: Path):
        self.rules: list[dict] = []
        self._groups: dict[str, set[str]] = {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._groups = {name: {_norm(d) for d in drugs} for name, drugs in data["groups"].items()}
            self.rules = data["rules"]
        except (OSError, ValueError, KeyError):
            pass  # optional data: without it the model and database decide alone

    def match(self, a_norm: str, b_norm: str) -> dict | None:
        """The strictest rule covering this pair (either drug in either group), or None."""
        found = None
        for rule in self.rules:
            first, second = self._groups.get(rule["a"], set()), self._groups.get(rule["b"], set())
            if (a_norm in first and b_norm in second) or (b_norm in first and a_norm in second):
                if found is None or rule["minimum"] == "Major":
                    found = rule
        return found
