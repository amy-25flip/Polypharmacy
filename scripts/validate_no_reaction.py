"""How often would the "No reaction" rule hide a real interaction?

Hold out 30% of the documented pairs (same split as the Evidence Passport calibration), retrain
Model 1 on the other 70%, and treat the held-out pairs as if the database had no record of them.
Every one of those pairs is a real interaction, so any held-out pair the rule would label "No
reaction" is a miss. The result is written to processed/no_reaction_validation.json and shown on
the transparency page.

Run from any directory: python scripts/validate_no_reaction.py
Limits: the chemistry second opinion is not applied (it can only add more caution), and the
drug-support counts come from the full dataset.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "webapp"))
from train_eval_severity_model import FEATURE_COLS, load_dataset, make_model  # noqa: E402
from evidence_passport import EvidencePassportEngine  # noqa: E402
from explainability import ExplainabilityEngine  # noqa: E402
from label_evidence import LabelEvidence  # noqa: E402
from severity_policy import resolve_severity, strong_mechanism  # noqa: E402

PROCESSED = ROOT / "processed"
OUTPUT = PROCESSED / "no_reaction_validation.json"


def main() -> None:
    df = load_dataset(PROCESSED / "polyguard_all_drugs_severity_pairs.csv")
    train, test = train_test_split(df, test_size=0.30, random_state=42, stratify=df["severity"])
    model = make_model()
    model.fit(train[FEATURE_COLS], train["severity"])
    proba = model.predict_proba(test[FEATURE_COLS])
    classes = list(model.classes_)
    labels = [classes[i] for i in proba.argmax(axis=1)]

    passport = EvidencePassportEngine(PROCESSED / "evidence_passport")
    explain = ExplainabilityEngine(PROCESSED / "explainability_data.json")
    ids = json.loads((PROCESSED / "drug_name_to_drugbank_id.json").read_text(encoding="utf-8"))
    labels_index = LabelEvidence(PROCESSED / "label_interactions.json")

    outcomes = defaultdict(Counter)  # true severity -> shown severity
    tiers = defaultdict(Counter)
    for row, p, label in zip(test.itertuples(index=False), proba, labels):
        a, b = row.pair_drug_1_norm, row.pair_drug_2_norm
        top2 = np.sort(p)[-2:]
        explanation = explain.explain_pair(ids.get(a), ids.get(b))
        card = passport.build(drug_a_norm=a, drug_b_norm=b, confidence=float(p.max()),
                              margin=float(top2[1] - top2[0]), is_documented=False,
                              has_mechanism_evidence=explanation["has_explanation"],
                              has_indirect_evidence=False)
        uncertain = card["abstain"] or card["reliability"]["band"] == "Low"
        shown, _ = resolve_severity(documented=None, model_severity=label, uncertain=uncertain,
                                    has_mechanism=strong_mechanism(explanation), estimated=False,
                                    has_label=bool(labels_index.get(a, b)))
        outcomes[row.severity][shown] += 1
        both_covered = (card["drug_a_support"]["tier"] == "well_represented"
                        and card["drug_b_support"]["tier"] == "well_represented")
        tiers[("both well covered" if both_covered else "at least one sparse or limited", row.severity)][shown] += 1

    # How wrong the model is on pairs the database does document (production model, its own training data).
    import joblib
    import pandas as pd
    production = joblib.load(PROCESSED / "model1_severity_pipeline.joblib")
    predicted = production.predict(df[FEATURE_COLS])
    wrong = predicted != df["severity"].to_numpy()
    major = (df["severity"] == "Major").to_numpy()
    model_alone = {"documented_pairs": int(len(df)), "model_wrong_pct": round(100 * float(wrong.mean()), 1),
                   "documented_major_pairs": int(major.sum()),
                   "major_shown_as_minor_pct": round(100 * float(((predicted == "Minor") & major).sum() / major.sum()), 1)}

    result = {"model_alone_on_documented_pairs": model_alone, "method": ("Model 1 retrained on a 70% split; the other 30% of documented pairs are treated as "
                         "unrecorded. All of them are real interactions, so 'No reaction' here is a miss."),
              "held_out_pairs": len(test), "by_true_severity": {}, "by_drug_coverage": {}}
    for severity in ("Major", "Moderate", "Minor"):
        counts = outcomes[severity]
        total = sum(counts.values())
        result["by_true_severity"][severity] = {
            "pairs": total, "shown_no_reaction_pct": round(100 * counts["None"] / total, 1),
            "shown_correctly_pct": round(100 * counts[severity] / total, 1),
            "shown_as": {k: round(100 * v / total, 1) for k, v in counts.items()}}
    for (coverage, severity), counts in sorted(tiers.items()):
        total = sum(counts.values())
        result["by_drug_coverage"].setdefault(coverage, {})[severity] = {
            "pairs": total, "shown_no_reaction_pct": round(100 * counts["None"] / total, 1)}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
