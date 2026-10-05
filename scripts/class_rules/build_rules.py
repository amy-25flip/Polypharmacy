"""Write processed/class_interaction_rules.json: class-level interaction floors from FDA label warnings.

Run from any directory: python scripts/class_rules/build_rules.py
A rule raises the severity of an UNDOCUMENTED pair to at least `minimum`; documented pairs keep their own
severity. Edit RULES and re-run to change what the app shows. A pharmacist has not yet reviewed these.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "processed" / "class_interaction_rules.json"


def label(drug: str) -> dict:
    return {"source": f"FDA {drug} label",
            "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={drug.lower().replace(' ', '+')}"}


GROUPS = {
    "ace_inhibitors": ["Enalapril", "Ramipril", "Lisinopril", "Perindopril", "Captopril", "Benazepril", "Fosinopril", "Quinapril", "Trandolapril"],
    "arbs": ["Losartan", "Telmisartan", "Valsartan", "Olmesartan", "Irbesartan", "Candesartan", "Eprosartan"],
    "potassium_raisers": ["Spironolactone", "Eplerenone", "Amiloride", "Triamterene", "Potassium chloride"],
    "nsaids": ["Ibuprofen", "Diclofenac", "Naproxen", "Ketorolac", "Celecoxib", "Etoricoxib", "Aceclofenac", "Meloxicam", "Indomethacin",
               "Piroxicam", "Nimesulide", "Mefenamic acid", "Ketoprofen"],
    "nitrates": ["Nitroglycerin", "Isosorbide mononitrate", "Isosorbide dinitrate"],
    "pde5_inhibitors": ["Sildenafil", "Tadalafil", "Vardenafil"],
    "opioids": ["Morphine", "Codeine", "Tramadol", "Fentanyl", "Oxycodone", "Hydromorphone", "Methadone", "Meperidine", "Tapentadol", "Buprenorphine"],
    "benzodiazepines": ["Diazepam", "Alprazolam", "Lorazepam", "Clonazepam", "Midazolam", "Temazepam", "Chlordiazepoxide", "Clobazam", "Triazolam"],
    "serotonergic": ["Sertraline", "Fluoxetine", "Paroxetine", "Escitalopram", "Citalopram", "Venlafaxine", "Duloxetine", "Fluvoxamine", "Tramadol"],
    "linezolid": ["Linezolid"],
}

RULES = [
    {"a": "ace_inhibitors", "b": "potassium_raisers", "minimum": "Moderate", "effects": ["High potassium"],
     "notice": "ACE inhibitors raise potassium, and so do potassium-sparing diuretics and potassium salts. Risk is higher in kidney disease, diabetes and older adults. Check potassium and kidney function.",
     **label("Lisinopril")},
    {"a": "arbs", "b": "potassium_raisers", "minimum": "Moderate", "effects": ["High potassium"],
     "notice": "ARBs raise potassium, and so do potassium-sparing diuretics and potassium salts. Risk is higher in kidney disease, diabetes and older adults. Check potassium and kidney function.",
     **label("Losartan")},
    {"a": "ace_inhibitors", "b": "nsaids", "minimum": "Moderate", "effects": ["Kidney injury", "Reduced effect"],
     "notice": "NSAIDs can blunt the blood-pressure effect and worsen kidney function, mostly with dehydration, kidney disease or a diuretic. Avoid prolonged use and check kidney function.",
     **label("Lisinopril")},
    {"a": "arbs", "b": "nsaids", "minimum": "Moderate", "effects": ["Kidney injury", "Reduced effect"],
     "notice": "NSAIDs can blunt the blood-pressure effect and worsen kidney function, mostly with dehydration, kidney disease or a diuretic. Avoid prolonged use and check kidney function.",
     **label("Losartan")},
    {"a": "ace_inhibitors", "b": "arbs", "minimum": "Moderate", "effects": ["High potassium", "Low blood pressure", "Kidney injury"],
     "notice": "Taking an ACE inhibitor and an ARB together raises the risk of high potassium, low blood pressure and kidney injury without added benefit.", **label("Lisinopril")},
    {"a": "nitrates", "b": "pde5_inhibitors", "minimum": "Major", "effects": ["Low blood pressure"],
     "notice": "Contraindicated: can cause a sudden, severe fall in blood pressure.", **label("Sildenafil")},
    {"a": "opioids", "b": "benzodiazepines", "minimum": "Major", "effects": ["Respiratory depression", "Sedation"],
     "notice": "Boxed warning: together they can cause profound sedation, slow breathing, coma and death. Avoid unless there is no alternative, and use the lowest doses for the shortest time.",
     **label("Tramadol")},
    {"a": "linezolid", "b": "serotonergic", "minimum": "Major", "effects": ["Serotonin syndrome"],
     "notice": "Linezolid blocks monoamine oxidase. With serotonergic medicines it can cause serotonin syndrome (agitation, fever, tremor).", **label("Linezolid")},
]


def main() -> None:
    vocabulary = set(json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8")))
    missing = sorted({d for drugs in GROUPS.values() for d in drugs if d not in vocabulary})
    if missing:
        raise SystemExit(f"Not in the vocabulary: {missing}")
    known = set(GROUPS)
    if any(rule[side] not in known for rule in RULES for side in ("a", "b")):
        raise SystemExit("A rule names an unknown group")
    OUTPUT.write_text(json.dumps({"groups": GROUPS, "rules": RULES, "note": "Floors for undocumented pairs only; from FDA label "
                                  "warnings; not yet reviewed by a pharmacist."}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: {len(RULES)} class rules over {len(GROUPS)} groups -> {OUTPUT}")


if __name__ == "__main__":
    main()
