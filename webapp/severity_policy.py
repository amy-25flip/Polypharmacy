"""One rule for the severity a doctor sees, shared by /api/check and the diagnosis planner.

Model 1 only ever learned from pairs that DO interact, so it has no "no reaction" answer and
it gets roughly 3 in 10 documented pairs wrong even on its own training data (including
documented Major pairs shown as Minor). The reference database is therefore consulted first:

1. documented pair            -> the documented severity (model is not used)
2. undocumented pair, model has a confident Moderate/Major, or the knowledge graph shows a
   shared class or target gene
                              -> the model's estimate, labelled "inferred"
3. undocumented, no mechanism, and the model says Minor or is not reliable
                              -> "None": no reaction on record (absence of a record, not
                                 proof of safety)
"""
from __future__ import annotations

import json
from pathlib import Path

RANK = {"None": -1, "Minor": 0, "Moderate": 1, "Major": 2}

BASIS_DOCUMENTED = "documented"
BASIS_ESTIMATED = "estimated"
BASIS_INFERRED = "inferred"
BASIS_NO_RECORD = "no_record"
BASIS_DUPLICATE = "duplicate_class"

NO_RECORD_NOTICE = (
    "No interaction is recorded for this pair in the reference database. This means no "
    "recorded reaction, not proof that the combination is safe."
)
DUPLICATE_NOTICE = (
    "These two medicines belong to the same class. Taking both is therapeutic duplication, "
    "which usually adds risk without extra benefit."
)


def load_documented_severity(path: Path) -> dict[str, str]:
    """``"a|b" (normalized, sorted) -> Minor/Moderate/Major`` for every documented pair."""
    grouped = json.loads(path.read_text(encoding="utf-8"))
    return {key: severity for severity, keys in grouped.items() for key in keys}


def strong_mechanism(explanation: dict) -> bool:
    """A shared drug class or shared target gene. Shared side effects alone are common to
    almost any two drugs (19% of random unrecorded pairs, 28-32% of documented ones), so
    they do not count as a reason to withhold a "no reaction" result."""
    reason = explanation.get("primary_reason")
    return bool(explanation.get("has_explanation") and reason and reason["type"] in ("class", "gene"))


def resolve_severity(*, documented: str | None, model_severity: str, uncertain: bool,
                     has_mechanism: bool, estimated: bool) -> tuple[str, str]:
    """Return ``(severity, basis)``; ``uncertain`` means the model abstained or is Low-reliability."""
    if documented:
        return documented, BASIS_ESTIMATED if estimated else BASIS_DOCUMENTED
    if not has_mechanism and (model_severity == "Minor" or uncertain):
        return "None", BASIS_NO_RECORD
    return model_severity, BASIS_INFERRED
