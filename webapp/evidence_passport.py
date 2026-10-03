"""
Evidence Passport + Selective Prediction.

Separates four things that a raw severity label collapses into one number:

  model confidence  !=  dataset coverage  !=  mechanism evidence  !=  clinical proof

All thresholds/curves here are loaded from files produced by
scripts/evidence_passport/build_calibration.py and build_support_index.py -
real empirical numbers from a held-out 30% split of the production dataset,
not guessed constants. See MODEL4_GNN_FINDINGS.md for the reasoning behind this design.
"""
from __future__ import annotations

import json
from pathlib import Path


class EvidencePassportEngine:
    def __init__(self, data_dir: Path):
        with open(data_dir / "calibration_bins.json", encoding="utf-8") as f:
            self.calibration_bins: list[dict] = json.load(f)
        with open(data_dir / "thresholds.json", encoding="utf-8") as f:
            self.thresholds: dict = json.load(f)
        with open(data_dir / "drug_support_counts.json", encoding="utf-8") as f:
            self.support_counts: dict[str, int] = json.load(f)
        with open(data_dir / "support_tiers.json", encoding="utf-8") as f:
            self.support_tiers: dict = json.load(f)

    def _reliability(self, confidence: float) -> dict:
        """Look up the empirical (held-out, measured) accuracy for predictions
        at this confidence level, from the calibration curve."""
        for b in self.calibration_bins:
            if b["confidence_low"] <= confidence < b["confidence_high"] + 1e-9:
                empirical_accuracy = b["empirical_accuracy"]
                break
        else:
            empirical_accuracy = self.calibration_bins[-1]["empirical_accuracy"] if confidence >= 0.95 else self.calibration_bins[0]["empirical_accuracy"]

        if empirical_accuracy >= 0.75:
            band = "High"
        elif empirical_accuracy >= 0.55:
            band = "Moderate"
        else:
            band = "Low"
        return {"band": band, "empirical_accuracy": empirical_accuracy}

    def _support_tier(self, drug_name_norm: str) -> dict:
        count = self.support_counts.get(drug_name_norm, 0)
        if count <= self.support_tiers["sparse_max"]:
            tier = "sparse"
        elif count <= self.support_tiers["limited_max"]:
            tier = "limited"
        else:
            tier = "well_represented"
        return {"documented_pair_count": count, "tier": tier}

    def build(
        self,
        drug_a_norm: str,
        drug_b_norm: str,
        confidence: float,
        margin: float,
        is_documented: bool,
        has_mechanism_evidence: bool,
        has_indirect_evidence: bool,
    ) -> dict:
        if is_documented:
            evidence_tier = "documented"
        elif has_mechanism_evidence:
            evidence_tier = "mechanism_evidence"
        elif has_indirect_evidence:
            evidence_tier = "indirect_evidence"
        else:
            evidence_tier = "no_evidence"

        reliability = self._reliability(confidence)

        # Selective prediction: only abstain on undocumented pairs - a documented
        # pair has a real labeled example, not just a model guess, so it's never
        # abstained on regardless of confidence.
        abstain = False
        abstain_reason = None
        if not is_documented:
            if confidence < self.thresholds["confidence_threshold"]:
                abstain = True
                abstain_reason = (
                    f"Model confidence ({confidence:.0%}) falls in a range where held-out "
                    f"testing showed only ~{reliability['empirical_accuracy']:.0%} accuracy - "
                    f"too low to present as a reliable severity estimate."
                )
            elif margin < self.thresholds["margin_threshold"]:
                abstain = True
                abstain_reason = (
                    "The model is nearly as confident in a different severity level for this "
                    "pair as it is in the one shown - the prediction is too ambiguous to present "
                    "as a reliable severity estimate."
                )

        return {
            "evidence_tier": evidence_tier,
            "drug_a_support": self._support_tier(drug_a_norm),
            "drug_b_support": self._support_tier(drug_b_norm),
            "reliability": reliability,
            "abstain": abstain,
            "abstain_reason": abstain_reason,
        }
