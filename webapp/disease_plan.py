"""Disease reference browsing and fast, pairwise medication-plan screening."""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from severity_policy import (
    BASIS_DUPLICATE, BASIS_INFERRED, BASIS_NO_DATA, apply_class_rule, BASIS_NO_RECORD, DUPLICATE_NOTICE, NO_RECORD_NOTICE, RANK,
    no_data_notice,
    resolve_severity, strong_mechanism,
)

ADVERSE_EFFECT_BASIS = (
    "Side effects both medicines are individually reported to cause (overlap of known "
    "side-effect profiles) - not an observed outcome of this specific combination."
)
FEATURE_COLS = ["pair_text", "disease_diabetes", "disease_ckd", "disease_heart_failure", "disease_hypertension"]


class DiseasePlanEngine:
    def __init__(self, data_path: Path, vocabulary: list[str], name_to_id: dict[str, str],
                 documented_pairs: set[str], model, explain_engine, passport_engine,
                 disagreement_sentinel, aliases, documented_severity: dict[str, str], label_evidence, class_rules):
        self.unavailable_reason: str | None = None
        self.vocab_by_norm = {self.normalize(name): name for name in vocabulary}
        self.name_to_id = name_to_id
        self.documented_pairs = documented_pairs
        self.model = model
        self.explain = explain_engine
        self.passport = passport_engine
        self.sentinel = disagreement_sentinel
        self.aliases = aliases
        self.documented_severity = documented_severity
        self.labels = label_evidence
        self.class_rules = class_rules
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

    def specialties(self) -> list[dict]:
        """Specialties with the number of diagnoses listed under each (alphabetical)."""
        counts: dict[str, int] = {}
        for disease in self.diseases.values():
            for specialty in disease.get("specialties", []):
                counts[specialty] = counts.get(specialty, 0) + 1
        return [{"name": name, "disease_count": counts[name]} for name in sorted(counts, key=str.casefold)]

    def search(self, query: str, specialty: str | None = None) -> list[dict]:
        q = self.normalize(query)
        diseases = list(self.diseases.values())
        if specialty:
            diseases = [d for d in diseases if specialty in d.get("specialties", [])]
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
                 "specialties": d.get("specialties", []),
                 "note": d.get("note"), "route_note": d.get("route_note"),
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
    def _pair_result(self, a: str, b: str, model_severity: str, probabilities: tuple[float, ...],
                     estimated: bool) -> dict:
        key = "|".join((a, b))
        documented_label = self.documented_severity.get(key)
        documented = documented_label is not None and not estimated
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
        label_entries = self.labels.get(a, b)
        severity, basis = resolve_severity(
            documented=documented_label, model_severity=model_severity, uncertain=bool(uncertain),
            has_mechanism=strong_mechanism(explanation), estimated=estimated,
            has_label=self.labels.has_mention(a, b),
        )
        rule = self.class_rules.match(a, b)
        severity, basis, class_notice = apply_class_rule(severity, basis, rule)
        # Effects named in an FDA label for this exact pair beat the overlap of each drug's own
        # side effects, which says nothing about the combination.
        label_effects = self.labels.effects(label_entries)
        if class_notice:
            label_effects = list(rule["effects"])
        if severity == "None":
            effects, source = (), "none"
        elif label_effects:
            effects, source = tuple(label_effects), "label"
        else:
            effects, source = self._adverse_effects(a, b), "overlap"
        return {"severity": severity, "severity_basis": basis, "is_documented": documented,
                # "Low confidence" only describes the model's own estimate.
                "uncertain": basis == BASIS_INFERRED and bool(uncertain),
                "adverse_effects": effects, "adverse_effect_source": source,
                "label_evidence": tuple(label_entries),
                **({"severity_notice": class_notice} if class_notice else {})}

    def screen(self, selected_raw: list[str], candidates_raw: list[str]) -> dict:
        selected, unmatched_a = self._resolve(selected_raw)
        candidates, unmatched_b = self._resolve(candidates_raw)
        selected_norm = {self.normalize(n) for n in selected}
        # Drugs with no records of their own are checked through a close relative.
        effective = {name: self.normalize(self.aliases.effective(name)) for name in (*selected, *candidates)}

        def same_drug(a: str, b: str) -> bool:
            return effective[a] == effective[b]

        def not_checked(a: str, b: str) -> bool:
            return bool(self.aliases.limited_notes(a, b))

        needed = set()
        for a, b in combinations(selected, 2):
            if not same_drug(a, b) and not not_checked(a, b):
                needed.add(self.pair_key(effective[a], effective[b]))
        for c in candidates:
            if self.normalize(c) not in selected_norm:
                for s in selected:
                    if not same_drug(c, s) and not not_checked(c, s):
                        needed.add(self.pair_key(effective[c], effective[s]))

        # One vectorized Model 1 pass for all uncached pairs. Documented pairs take their
        # documented severity (see severity_policy); the model covers the rest.
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
            limited = self.aliases.limited_notes(a, b)
            if limited:
                return {"severity": "None", "severity_basis": BASIS_NO_DATA, "is_documented": False,
                        "uncertain": False, "adverse_effects": (), "estimated_from": [],
                        "adverse_effect_source": "none", "label_evidence": (),
                        "severity_notice": no_data_notice(limited)}
            notes = self.aliases.notes(a, b)
            if same_drug(a, b):
                return {"severity": "Moderate", "severity_basis": BASIS_DUPLICATE, "is_documented": False,
                        "uncertain": False, "adverse_effects": (), "estimated_from": notes,
                        "adverse_effect_source": "none", "label_evidence": (),
                        "severity_notice": DUPLICATE_NOTICE}
            key = self.pair_key(effective[a], effective[b])
            label, proba = self._prediction_cache[key]
            result = dict(self._pair_result(*key, label, proba, bool(notes)))
            result["estimated_from"] = notes
            if result["severity_basis"] == BASIS_NO_RECORD:
                result["severity_notice"] = NO_RECORD_NOTICE
            return result

        selected_pairs = []
        counts = {"Major": 0, "Moderate": 0, "Minor": 0, "None": 0}
        for a, b in combinations(selected, 2):
            p = pair(a, b)
            counts[p["severity"]] += 1
            selected_pairs.append({"drug_a": a, "drug_b": b, **{k: (list(v[:5]) if k == "adverse_effects"
                                                                      else list(v) if k == "label_evidence" else v)
                                                              for k, v in p.items()}})
        selected_pairs.sort(key=lambda p: (-RANK[p["severity"]], p["drug_a"], p["drug_b"]))

        results = []
        for c in candidates:
            flags = []
            if self.normalize(c) not in selected_norm:
                for s in selected:
                    p = pair(c, s)
                    flags.append({"with": s, "severity": p["severity"], "severity_basis": p["severity_basis"],
                                  "is_documented": p["is_documented"], "uncertain": p["uncertain"],
                                  "estimated_from": p["estimated_from"],
                                  "severity_notice": p.get("severity_notice"),
                                  "adverse_effect_source": p["adverse_effect_source"],
                                  "label_evidence": list(p["label_evidence"]),
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
