"""Cautions that depend on the patient's age or kidney function (decision support only).

Rules come from processed/patient_factor_rules.json (built by scripts/patient_factors/build_rules.py).
They never change an interaction severity; they are listed beside the medicines they concern.
"""
from __future__ import annotations

import json
from pathlib import Path

LEVEL_ORDER = {"Avoid": 0, "Adjust dose": 1, "Use with caution": 2}


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().split())


class PatientFactorEngine:
    def __init__(self, path: Path):
        self.rules: list[dict] = []
        try:
            self.rules = json.loads(path.read_text(encoding="utf-8"))["rules"]
        except (OSError, ValueError, KeyError):
            pass  # optional data: the feature simply reports no cautions

    def cautions(self, drugs: list[str], age: int | None, egfr: int | None, pregnant: bool | None = None) -> list[dict]:
        """``egfr`` is the lower edge of the band the doctor picked, so "below 45" includes 30-44."""
        found: dict[tuple[str, str], dict] = {}
        for drug in drugs:
            name = _norm(drug)
            for rule in self.rules:
                if name not in {_norm(d) for d in rule["drugs"]}:
                    continue
                if rule["factor"] == "egfr" and egfr is not None and egfr < rule["below"]:
                    trigger = f"eGFR below {rule['below']}"
                elif rule["factor"] == "age" and age is not None and age >= rule["at_least"]:
                    trigger = f"age {rule['at_least']} or over"
                elif rule["factor"] == "pregnancy" and pregnant:
                    trigger = "pregnant or may become pregnant"
                else:
                    continue
                key = (name, rule["factor"])
                existing = found.get(key)
                # Keep the strictest applicable rule per medicine and factor.
                if existing and LEVEL_ORDER[existing["level"]] <= LEVEL_ORDER[rule["level"]]:
                    continue
                found[key] = {"drug": drug, "level": rule["level"], "factor": rule["factor"], "trigger": trigger,
                              "text": rule["text"], "source": rule["source"], "url": rule["url"]}
        return sorted(found.values(), key=lambda c: (LEVEL_ORDER[c["level"]], c["drug"].casefold()))
