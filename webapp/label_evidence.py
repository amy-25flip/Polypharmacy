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
        # Only real sentences are shown. A table row or a long list of drug names says nothing
        # readable about the pair, but it still counts as a mention (see has_mention).
        sentences = sorted((e for e in entries if not e.get("list")), key=lambda e: (not e["effects"], e["from"]))
        return sentences[:MAX_ENTRIES]

    def has_mention(self, a_norm: str, b_norm: str) -> bool:
        """True if either drug's label names the other, even only in a table or list."""
        return bool(self.pairs.get("|".join(sorted((a_norm, b_norm)))))

    @staticmethod
    def effects(entries: list[dict]) -> list[str]:
        return list(dict.fromkeys(effect for entry in entries for effect in entry["effects"]))[:6]
