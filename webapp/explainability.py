from __future__ import annotations

import json
from pathlib import Path

CATEGORY_COEFFICIENTS = {
    "class": 4.0,
    "side_effect": 3.0,
    "gene": 2.5,
}

CATEGORY_LABELS = {
    "class": "shared drug class",
    "side_effect": "shared adverse-effect evidence",
    "gene": "shared biological target",
}

MAX_ITEMS_PER_CATEGORY = 3


class ExplainabilityEngine:
    def __init__(self, data_path: Path):
        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)
        self.genes: dict[str, list[str]] = data["genes"]
        self.side_effects: dict[str, list[str]] = data["side_effects"]
        self.classes: dict[str, list[str]] = data["classes"]
        self.resembles: dict[str, list[str]] = data["resembles"]
        self.gene_weights: dict[str, float] = data["gene_weights"]
        self.side_effect_weights: dict[str, float] = data["side_effect_weights"]
        self.class_weights: dict[str, float] = data["class_weights"]
        self.item_names: dict[str, str] = data["item_names"]

    def _name(self, item_id: str) -> str:
        return self.item_names.get(item_id, item_id)

    def _category_overlap(
        self, drug_a_id: str, drug_b_id: str, drug_to_items: dict[str, list[str]], weights: dict[str, float]
    ) -> tuple[float, list[tuple[str, float]]]:
        items_a = set(drug_to_items.get(drug_a_id, []))
        items_b = set(drug_to_items.get(drug_b_id, []))
        shared = items_a & items_b
        if not shared:
            return 0.0, []
        weighted = sorted(
            ((item, weights.get(item, 0.0)) for item in shared),
            key=lambda pair: pair[1],
            reverse=True,
        )
        total_score = sum(w for _, w in weighted)
        return total_score, weighted[:MAX_ITEMS_PER_CATEGORY]

    def explain_pair(self, drug_a_id: str | None, drug_b_id: str | None) -> dict:
        coverage = {
            "drug_a_has_kg_data": bool(drug_a_id and (
                drug_a_id in self.genes or drug_a_id in self.side_effects or drug_a_id in self.classes
            )),
            "drug_b_has_kg_data": bool(drug_b_id and (
                drug_b_id in self.genes or drug_b_id in self.side_effects or drug_b_id in self.classes
            )),
        }

        if not drug_a_id or not drug_b_id:
            return {
                "has_explanation": False,
                "primary_reason": None,
                "supporting_evidence": [],
                "coverage": coverage,
                "caveat": "This is knowledge-graph evidence, not a confirmed patient-specific mechanism.",
            }

        category_results: dict[str, tuple[float, list[tuple[str, float]]]] = {
            "class": self._category_overlap(drug_a_id, drug_b_id, self.classes, self.class_weights),
            "side_effect": self._category_overlap(drug_a_id, drug_b_id, self.side_effects, self.side_effect_weights),
            "gene": self._category_overlap(drug_a_id, drug_b_id, self.genes, self.gene_weights),
        }

        weighted_scores = {
            cat: score * CATEGORY_COEFFICIENTS[cat] for cat, (score, _) in category_results.items()
        }
        ranked_categories = sorted(
            (cat for cat, score in weighted_scores.items() if score > 0),
            key=lambda cat: weighted_scores[cat],
            reverse=True,
        )

        resembles_flag = drug_b_id in self.resembles.get(drug_a_id, [])

        if not ranked_categories:
            return {
                "has_explanation": False,
                "primary_reason": None,
                "supporting_evidence": (
                    [{"type": "structural_resemblance", "items": ["Structurally similar compounds"]}]
                    if resembles_flag else []
                ),
                "coverage": coverage,
                "caveat": "This is knowledge-graph evidence, not a confirmed patient-specific mechanism.",
            }

        top_category = ranked_categories[0]
        _, top_items = category_results[top_category]
        top_item_names = [self._name(item) for item, _ in top_items]

        primary_reason = {
            "type": top_category,
            "title": CATEGORY_LABELS[top_category].capitalize(),
            "plain_text": self._plain_text(top_category, top_item_names),
            "evidence": top_item_names,
        }

        supporting_evidence = []
        for cat in ranked_categories[1:]:
            _, items = category_results[cat]
            supporting_evidence.append(
                {"type": cat, "items": [self._name(item) for item, _ in items]}
            )
        if resembles_flag:
            supporting_evidence.append(
                {"type": "structural_resemblance", "items": ["Structurally similar compounds"]}
            )

        return {
            "has_explanation": True,
            "primary_reason": primary_reason,
            "supporting_evidence": supporting_evidence,
            "coverage": coverage,
            "caveat": "This is knowledge-graph evidence, not a confirmed patient-specific mechanism.",
        }

    @staticmethod
    def _plain_text(category: str, item_names: list[str]) -> str:
        joined = ", ".join(item_names)
        if category == "class":
            return f"Both medicines belong to the same drug class ({joined}), which can raise the risk of combined or additive effects."
        if category == "side_effect":
            return f"Both medicines are linked to overlapping effects ({joined}), so combining them may increase that risk."
        if category == "gene":
            return f"Both medicines interact with the same biological target ({joined}), which may contribute to the interaction."
        return f"Related evidence found: {joined}."
