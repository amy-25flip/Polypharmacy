"""Pair-specific evidence taken from FDA drug-label text.

processed/label_interactions.json (built by scripts/fda_labels/build_label_evidence.py) holds, for
pairs where one drug's FDA label names the other in its interactions section, the sentence that
does so and the adverse effects that sentence names. This is the only pair-specific adverse-effect
data in the app; everything else is the overlap of each drug's own side effects.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_ENTRIES = 3


class LabelEvidence:
    def __init__(self, path: Path):
        self.pairs: dict[str, list[dict]] = {}
        self.source = ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.pairs = data["pairs"]
            self.source = data.get("source", "")
        except (OSError, ValueError, KeyError):
            pass  # optional data: without it the app falls back to the side-effect overlap

    def get(self, a_norm: str, b_norm: str) -> list[dict]:
        entries = self.pairs.get("|".join(sorted((a_norm, b_norm))), [])
        # Real sentences first. A table row or a long list of drug names is shown only when nothing
        # better exists, and then only once.
        sentences = sorted((e for e in entries if not e.get("list")), key=lambda e: (not e["effects"], e["from"]))
        chosen = sentences[:MAX_ENTRIES]
        if not chosen:
            chosen = [e for e in entries if e.get("list")][:1]
        return chosen

    @staticmethod
    def effects(entries: list[dict]) -> list[str]:
        return list(dict.fromkeys(effect for entry in entries for effect in entry["effects"]))[:6]
