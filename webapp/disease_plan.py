"""Disease reference browsing and fast, pairwise medication-plan screening."""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz


RANK = {"Minor": 0, "Moderate": 1, "Major": 2}
ADVERSE_EFFECT_BASIS = (
    "Side effects both medicines are individually reported to cause (overlap of known "
    "side-effect profiles) - not an observed outcome of this specific combination."
)
FEATURE_COLS = ["pair_text", "disease_diabetes", "disease_ckd", "disease_heart_failure", "disease_hypertension"]


class DiseasePlanEngine:
    def __init__(self, data_path: Path, vocabulary: list[str], name_to_id: dict[str, str],
                 documented_pairs: set[str], model, explain_engine, passport_engine,
                 disagreement_sentinel):
        self.unavailable_reason: str | None = None
        self.vocab_by_norm = {self.normalize(name): name for name in vocabulary}
        self.name_to_id = name_to_id
        self.documented_pairs = documented_pairs
        self.model = model
        self.explain = explain_engine
        self.passport = passport_engine
        self.sentinel = disagreement_sentinel
        self._prediction_cache: dict[tuple[str, str], tuple[str, tuple[float, ...]]] = {}
        self.diseases: dict[str, dict] = {}
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("diseases"), list):
                raise ValueError("unsupported or malformed formulary")
            for disease in data["diseases"]:
                if not all(k in disease for k in ("id", "name", "aliases", "medicines")):
                    raise ValueError("malformed disease entry")
                if (not isinstance(disease["id"], str) or not isinstance(disease["name"], str)
                        or not isinstance(disease["aliases"], list)
                        or not all(isinstance(a, str) for a in disease["aliases"])
                        or not isinstance(disease["medicines"], list)):
                    raise ValueError("malformed medicines")
                for med in disease["medicines"]:
                    if (not isinstance(med, dict) or med.get("name") not in self.vocab_by_norm.values()
                            or not isinstance(med.get("sources"), list)
                            or not med["sources"] or not all(isinstance(s, str) for s in med["sources"])):
                        raise ValueError("formulary contains an unknown medicine or missing provenance")
                self.diseases[disease["id"]] = disease
            if not self.diseases:
                raise ValueError("empty formulary")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.unavailable_reason = f"Disease plan feature unavailable: {exc}"

    @staticmethod
    def normalize(name: str) -> str:
        return " ".join(name.strip().lower().split())

    @staticmethod
    def pair_key(a: str, b: str) -> tuple[str, str]:
        return tuple(sorted((a, b)))

    def search(self, query: str) -> list[dict]:
        q = self.normalize(query)
        diseases = list(self.diseases.values())
        if not q:
            ordered = sorted(diseases, key=lambda d: (-len(d["medicines"]), d["name"].casefold()))
        else:
            def terms(d):
                return [self.normalize(d["name"]), *(self.normalize(a) for a in d["aliases"])]
            prefix = [d for d in diseases if any(t.startswith(q) for t in terms(d))]
            substring = [d for d in diseases if d not in prefix and any(q in t for t in terms(d))]
            prefix.sort(key=lambda d: d["name"].casefold())
            substring.sort(key=lambda d: d["name"].casefold())
            ordered = prefix + substring
            # Fuzzy matching is only a typo fallback. Running it alongside a real
            # prefix/substring hit padded results with unrelated diseases
            # (a "diabetes" search surfaced dilated cardiomyopathy).
            if not ordered:
                # Score each name/alias on its own (and each long word within it). Scoring
                # one long joined string made typos land on unrelated diseases.
                def best_score(d):
                    ts = terms(d)
                    words = [w for t in ts for w in t.split() if len(w) > 3]
                    return max(max(fuzz.WRatio(q, t) for t in ts),
                               max((fuzz.ratio(q, w) for w in words), default=0))
                scored = sorted(((best_score(d), d) for d in diseases),
                                key=lambda item: (-item[0], item[1]["name"].casefold()))
                ordered = [d for score, d in scored[:8] if score >= 78]
        return [{"id": d["id"], "name": d["name"], "aliases": d["aliases"],
                 "medicine_count": len(d["medicines"])} for d in ordered]

    def medicines(self, disease_id: str) -> dict | None:
        d = self.diseases.get(disease_id)
        return {"disease": {"id": d["id"], "name": d["name"]}, "medicines": d["medicines"]} if d else None

    def _resolve(self, names: list[str]) -> tuple[list[str], list[str]]:
        matched, unmatched, seen = [], [], set()
        for raw in names:
            norm = self.normalize(raw)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            canonical = self.vocab_by_norm.get(norm)
            (matched if canonical else unmatched).append(canonical or raw.strip())
        return matched, unmatched

    def _adverse_effects(self, a: str, b: str) -> tuple[str, ...]:
        id_a, id_b = self.name_to_id.get(a), self.name_to_id.get(b)
        if not id_a or not id_b:
            return ()
        shared = set(self.explain.side_effects.get(id_a, ())) & set(self.explain.side_effects.get(id_b, ()))
        ranked = sorted(shared, key=lambda item: (-self.explain.side_effect_weights.get(item, 0),
                                                   self.explain.item_names.get(item, item).casefold()))
        return tuple(dict.fromkeys(self.explain.item_names.get(item, item) for item in ranked))

    @lru_cache(maxsize=100_000)
    def _pair_result(self, a: str, b: str, severity: str, probabilities: tuple[float, ...]) -> dict:
        key = "|".join((a, b))
        documented = key in self.documented_pairs
        proba = np.asarray(probabilities)
        confidence = float(np.max(proba))
        top2 = np.sort(proba)[-2:]
        explanation = self.explain.explain_pair(self.name_to_id.get(a), self.name_to_id.get(b))
        passport = self.passport.build(
            drug_a_norm=a, drug_b_norm=b, confidence=confidence,
            margin=float(top2[1] - top2[0]), is_documented=documented,
            has_mechanism_evidence=explanation["has_explanation"],
            has_indirect_evidence=bool(explanation["supporting_evidence"]) and not explanation["has_explanation"],
        )
        # Same selective-prediction rule as /api/check. The chemistry sentinel is
        # only needed when the ordinary passport did not already abstain.
        uncertain = passport["abstain"] or passport["reliability"]["band"] == "Low"
        if not documented and not uncertain and self.sentinel.has_coverage(a, b):
            agreement = self.sentinel.score(a, b, proba, list(self.model.classes_))
            uncertain = bool(agreement and agreement["disagreement_level"] == "High")
        return {"severity": severity, "is_documented": documented, "uncertain": bool(uncertain),
                "adverse_effects": self._adverse_effects(a, b)}

    def screen(self, selected_raw: list[str], candidates_raw: list[str]) -> dict:
        selected, unmatched_a = self._resolve(selected_raw)
        candidates, unmatched_b = self._resolve(candidates_raw)
        selected_norm = {self.normalize(n) for n in selected}
        needed = set()
        for a, b in combinations(selected, 2):
            needed.add(self.pair_key(self.normalize(a), self.normalize(b)))
        for c in candidates:
            if self.normalize(c) not in selected_norm:
                for s in selected:
                    needed.add(self.pair_key(self.normalize(c), self.normalize(s)))

        # One vectorized Model 1 pass for all uncached pairs. Documented status is
        # resolved from the exact index, while labels retain /api/check's model rule.
        ordered = sorted(needed)
        missing = [key for key in ordered if key not in self._prediction_cache]
        if missing:
            rows = pd.DataFrame({
                "pair_text": [" [DRUG_PAIR] ".join(key) + " [DISEASE_SCOPE] " for key in missing],
                "disease_diabetes": 0, "disease_ckd": 0,
                "disease_heart_failure": 0, "disease_hypertension": 0,
            })
            labels = self.model.predict(rows[FEATURE_COLS])
            probabilities = self.model.predict_proba(rows[FEATURE_COLS])
            for key, label, proba in zip(missing, labels, probabilities):
                self._prediction_cache[key] = (str(label), tuple(float(x) for x in proba))

        def pair(a: str, b: str) -> dict:
            key = self.pair_key(self.normalize(a), self.normalize(b))
            label, proba = self._prediction_cache[key]
            return self._pair_result(*key, label, proba)

        selected_pairs = []
        counts = {"Major": 0, "Moderate": 0, "Minor": 0}
        for a, b in combinations(selected, 2):
            p = pair(a, b)
            counts[p["severity"]] += 1
            selected_pairs.append({"drug_a": a, "drug_b": b, **{k: (list(v[:5]) if k == "adverse_effects" else v)
                                                              for k, v in p.items()}})
        selected_pairs.sort(key=lambda p: (-RANK[p["severity"]], p["drug_a"], p["drug_b"]))

        results = []
        for c in candidates:
            flags = []
            if self.normalize(c) not in selected_norm:
                for s in selected:
                    p = pair(c, s)
                    flags.append({"with": s, "severity": p["severity"],
                                  "is_documented": p["is_documented"], "uncertain": p["uncertain"],
                                  "adverse_effects": list(p["adverse_effects"][:5])})
            flags.sort(key=lambda p: (-RANK[p["severity"]], p["with"]))
            adverse = list(dict.fromkeys(effect for flag in flags for effect in flag["adverse_effects"]))[:6]
            results.append({"candidate": c, "worst_severity": flags[0]["severity"] if flags else None,
                            "flags": flags, "adverse_effects": adverse})
        return {"results": results,
                "selected_summary": {"overall_severity": selected_pairs[0]["severity"] if selected_pairs else None,
                                     "pairs": selected_pairs, "counts": counts},
                "unmatched": list(dict.fromkeys(unmatched_a + unmatched_b)),
                "adverse_effect_basis": ADVERSE_EFFECT_BASIS}
