"""
Model Disagreement Sentinel - live inference.

Repurposes Model 2 (chemistry, a documented negative result on its own -
CHEMISTRY_MODEL_FINDINGS.md) as an independent second opinion for Model 1.
Held-out testing (scripts/disagreement_sentinel/build_calibration.py) showed
a strong, real relationship between how much the two models disagree and how
often Model 1 is wrong: 84.5% accuracy when they closely agree, down to
13.3% when they sharply disagree (correlation 0.45). That calibration curve
is what this module looks up - it does not invent a heuristic.

Only available for pairs where both drugs have a resolved SMILES (chemistry
coverage) - about 38% of all pairs. When unavailable, the Evidence Passport
simply doesn't get this extra signal; everything else still works.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator

RDLogger.DisableLog("rdApp.*")

SEVERITY_ORDER = ["Minor", "Moderate", "Major"]


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    m = 0.5 * (p + q)
    def kl(a, b):
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


class DisagreementSentinel:
    def __init__(self, data_dir: Path):
        self.model2 = joblib.load(data_dir / "model2_chemistry_pipeline.joblib")
        with open(data_dir / "fingerprint_cache.json", encoding="utf-8") as f:
            cache = json.load(f)
        self.n_bits: int = cache["n_bits"]
        self._fp_indices: dict[str, list[int]] = cache["fingerprints"]
        with open(data_dir / "disagreement_calibration.json", encoding="utf-8") as f:
            self.calibration: dict = json.load(f)
        self._generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=self.n_bits)

    def has_coverage(self, drug_a_norm: str, drug_b_norm: str) -> bool:
        return drug_a_norm in self._fp_indices and drug_b_norm in self._fp_indices

    def _bits(self, drug_norm: str) -> np.ndarray:
        arr = np.zeros((self.n_bits,), dtype=np.float32)
        arr[self._fp_indices[drug_norm]] = 1.0
        return arr

    def _pair_features(self, drug_a_norm: str, drug_b_norm: str) -> np.ndarray:
        fp_a, fp_b = self._bits(drug_a_norm), self._bits(drug_b_norm)
        abs_diff = np.abs(fp_a - fp_b)
        and_ = np.minimum(fp_a, fp_b)
        or_ = np.maximum(fp_a, fp_b)
        product = fp_a * fp_b
        intersection, union = and_.sum(), or_.sum()
        tanimoto = np.array([intersection / union if union > 0 else 0.0])
        return np.concatenate([abs_diff, and_, or_, product, tanimoto]).reshape(1, -1).astype(np.float32)

    def _reliability_for_disagreement(self, js_div: float) -> dict:
        for b in self.calibration["bins"]:
            if b["js_divergence_low"] <= js_div < b["js_divergence_high"] + 1e-9:
                return b
        return self.calibration["bins"][-1]

    def score(self, drug_a_norm: str, drug_b_norm: str, proba1: np.ndarray, classes1: list[str]) -> dict | None:
        if not self.has_coverage(drug_a_norm, drug_b_norm):
            return None

        X = self._pair_features(drug_a_norm, drug_b_norm)
        proba2 = self.model2.predict_proba(X)[0]
        classes2 = list(self.model2.classes_)

        p1 = np.array([proba1[classes1.index(c)] for c in SEVERITY_ORDER])
        p2 = np.array([proba2[classes2.index(c)] for c in SEVERITY_ORDER])

        js_div = js_divergence(p1, p2)
        bin_info = self._reliability_for_disagreement(js_div)

        if bin_info["model1_empirical_accuracy"] >= 0.75:
            level = "Low"
        elif bin_info["model1_empirical_accuracy"] >= 0.55:
            level = "Moderate"
        else:
            level = "High"

        return {
            "available": True,
            "chemistry_model_severity": SEVERITY_ORDER[int(np.argmax(p2))],
            "js_divergence": round(js_div, 4),
            "disagreement_level": level,
            "model1_empirical_accuracy_at_this_disagreement": bin_info["model1_empirical_accuracy"],
        }
