"""Write processed/patient_factor_rules.json: cautions that depend on the patient's age or kidney function.

Run from any directory: python scripts/patient_factors/build_rules.py

Each rule says which medicines it covers, the factor and threshold that trigger it, what to do,
and where the advice comes from. Edit RULES below and re-run to change what the app shows. These
are decision-support cautions taken from published guidance; a clinician has not yet reviewed them.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "processed" / "patient_factor_rules.json"

BEERS = {"source": "2023 AGS Beers Criteria (older adults)", "url": "https://doi.org/10.1111/jgs.18372"}
KDIGO = {"source": "KDIGO CKD guideline (medication management)",
         "url": "https://kdigo.org/guidelines/ckd-evaluation-and-management/"}


def label(drug: str) -> dict:
    return {"source": f"FDA {drug} label",
            "url": f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query={drug.lower()}"}


NSAIDS = ["Ibuprofen", "Diclofenac", "Naproxen", "Ketorolac", "Celecoxib", "Indomethacin", "Meloxicam",
          "Piroxicam", "Etoricoxib", "Aceclofenac"]

RULES = [
    # --- kidney function (eGFR in mL/min/1.73 m2) ---
    {"drugs": ["Metformin"], "factor": "egfr", "below": 30, "level": "Avoid",
     "text": "Contraindicated when eGFR is below 30 (risk of lactic acidosis).", **label("Metformin")},
    {"drugs": ["Metformin"], "factor": "egfr", "below": 45, "level": "Use with caution",
     "text": "Starting metformin is not recommended at eGFR 30 to 44. If already taking it, weigh benefit against risk and consider a lower dose.",
     **label("Metformin")},
    {"drugs": NSAIDS, "factor": "egfr", "below": 30, "level": "Avoid",
     "text": "Avoid NSAIDs when eGFR is below 30 (further kidney injury and fluid retention).", **KDIGO},
    {"drugs": NSAIDS, "factor": "egfr", "below": 60, "level": "Use with caution",
     "text": "Avoid prolonged NSAID use at eGFR below 60, especially with an ACE inhibitor, ARB or diuretic.", **KDIGO},
    {"drugs": ["Nitrofurantoin"], "factor": "egfr", "below": 30, "level": "Avoid",
     "text": "Avoid when creatinine clearance is below 30 (poor urine levels and a higher risk of toxicity).", **BEERS},
    {"drugs": ["Eplerenone"], "factor": "egfr", "below": 30, "level": "Avoid",
     "text": "Contraindicated in hypertension when creatinine clearance is 30 or below (high potassium).", **label("Eplerenone")},
    {"drugs": ["Spironolactone"], "factor": "egfr", "below": 45, "level": "Use with caution",
     "text": "Risk of high potassium rises as kidney function falls. Check potassium and creatinine closely.",
     **label("Spironolactone")},
    {"drugs": ["Rivaroxaban"], "factor": "egfr", "below": 15, "level": "Avoid",
     "text": "Avoid when creatinine clearance is below 15.", **label("Rivaroxaban")},
    {"drugs": ["Enoxaparin"], "factor": "egfr", "below": 30, "level": "Adjust dose",
     "text": "Dose reduction is needed when creatinine clearance is below 30.", **label("Enoxaparin")},
    {"drugs": ["Digoxin"], "factor": "egfr", "below": 60, "level": "Adjust dose",
     "text": "Cleared by the kidneys. A lower dose and drug-level monitoring are usually needed.", **label("Digoxin")},
    {"drugs": ["Gabapentin", "Pregabalin"], "factor": "egfr", "below": 60, "level": "Adjust dose",
     "text": "Dose must be reduced as kidney function falls (accumulation causes drowsiness and confusion).",
     "source": "FDA gabapentin and pregabalin labels",
     "url": "https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query=gabapentin"},
    {"drugs": ["Colchicine"], "factor": "egfr", "below": 30, "level": "Adjust dose",
     "text": "Dose reduction is needed in severe kidney impairment; toxicity is more likely.", **label("Colchicine")},
    {"drugs": ["Lithium carbonate"], "factor": "egfr", "below": 60, "level": "Use with caution",
     "text": "Reduced clearance raises the risk of lithium toxicity. Monitor drug levels closely.", **label("Lithium")},
    {"drugs": ["Glyburide"], "factor": "egfr", "below": 60, "level": "Avoid",
     "text": "Long-acting sulfonylurea with active metabolites; prolonged low blood sugar is more likely when kidney function is reduced.",
     "source": "ADA Standards of Care and 2023 AGS Beers Criteria", "url": BEERS["url"]},
    {"drugs": ["Atenolol"], "factor": "egfr", "below": 35, "level": "Adjust dose",
     "text": "Cleared by the kidneys. Dose reduction is needed when creatinine clearance is below 35.", **label("Atenolol")},
    # --- age 65 and over ---
    {"drugs": ["Diazepam", "Alprazolam", "Lorazepam", "Clonazepam", "Chlordiazepoxide", "Temazepam"],
     "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Benzodiazepines raise the risk of falls, fractures, confusion and delirium in older adults.", **BEERS},
    {"drugs": ["Zolpidem", "Eszopiclone", "Zaleplon"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Sleep medicines of this kind carry the same risks of falls and confusion as benzodiazepines.", **BEERS},
    {"drugs": ["Chlorpheniramine", "Hydroxyzine", "Diphenhydramine", "Promethazine", "Cyproheptadine"],
     "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "First-generation antihistamines are strongly anticholinergic (confusion, urinary retention, constipation).", **BEERS},
    {"drugs": ["Amitriptyline", "Imipramine", "Clomipramine", "Doxepin"], "factor": "age", "at_least": 65,
     "level": "Avoid", "text": "Strongly anticholinergic and sedating, and can cause low blood pressure on standing.", **BEERS},
    {"drugs": ["Glyburide", "Chlorpropamide"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Higher risk of prolonged low blood sugar than other sulfonylureas.", **BEERS},
    {"drugs": ["Ketorolac"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Higher risk of stomach bleeding and kidney injury.", **BEERS},
    {"drugs": ["Ibuprofen", "Diclofenac", "Naproxen", "Indomethacin", "Meloxicam", "Piroxicam"],
     "factor": "age", "at_least": 65, "level": "Use with caution",
     "text": "Avoid long-term use unless alternatives have failed; higher risk of stomach bleeding, kidney injury and raised blood pressure.",
     **BEERS},
    {"drugs": ["Meperidine"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Not an effective pain medicine at usual doses and can cause confusion and seizures.", **BEERS},
    {"drugs": ["Cyclobenzaprine", "Methocarbamol", "Carisoprodol"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Poorly tolerated muscle relaxants (sedation, confusion, falls) with doubtful benefit.", **BEERS},
    {"drugs": ["Metoclopramide"], "factor": "age", "at_least": 65, "level": "Avoid",
     "text": "Can cause movement disorders; avoid unless treating gastroparesis.", **BEERS},
    {"drugs": ["Omeprazole", "Pantoprazole", "Esomeprazole", "Rabeprazole", "Lansoprazole"],
     "factor": "age", "at_least": 65, "level": "Use with caution",
     "text": "Avoid courses longer than 8 weeks unless there is a clear reason (fracture, C. difficile infection and low magnesium or B12).",
     **BEERS},
    # --- pregnancy (also when pregnancy is possible) ---
    {"drugs": ["Isotretinoin"], "factor": "pregnancy", "level": "Avoid",
     "text": "Causes serious birth defects. Contraindicated in pregnancy; needs a negative pregnancy test and effective contraception before, during and for a month after treatment.",
     **label("Isotretinoin")},
    {"drugs": ["Acitretin"], "factor": "pregnancy", "level": "Avoid",
     "text": "Causes severe birth defects. Contraindicated in pregnancy, and pregnancy must be avoided for at least 3 years after stopping. Alcohol must be avoided during and for 2 months after treatment.",
     **label("Acitretin")},
    {"drugs": ["Methotrexate"], "factor": "pregnancy", "level": "Avoid",
     "text": "Can cause fetal death and birth defects. Contraindicated in pregnancy for non-cancer uses such as psoriasis and arthritis.",
     **label("Methotrexate")},
    {"drugs": ["Thalidomide"], "factor": "pregnancy", "level": "Avoid",
     "text": "Causes severe, life-threatening birth defects. Use only under a pregnancy-prevention programme.", **label("Thalidomide")},
    {"drugs": ["Finasteride"], "factor": "pregnancy", "level": "Avoid",
     "text": "Can harm a male fetus. Women who are or may be pregnant must not take it or handle crushed tablets.", **label("Finasteride")},
    {"drugs": ["Mycophenolate mofetil"], "factor": "pregnancy", "level": "Avoid",
     "text": "Boxed warning for pregnancy loss and birth defects. Needs pregnancy testing and contraception.", **label("Mycophenolate")},
    {"drugs": ["Misoprostol"], "factor": "pregnancy", "level": "Avoid",
     "text": "Can cause abortion, premature birth and birth defects.", **label("Misoprostol")},
    {"drugs": ["Valproic acid"], "factor": "pregnancy", "level": "Avoid",
     "text": "Raises the risk of neural tube defects and lower IQ in the child. Use only if no alternative works.", **label("Valproate")},
    {"drugs": ["Warfarin"], "factor": "pregnancy", "level": "Avoid",
     "text": "Crosses the placenta and can cause birth defects and bleeding. Contraindicated except in women with mechanical heart valves, under specialist care.",
     **label("Warfarin")},
    {"drugs": ["Lisinopril", "Enalapril", "Ramipril", "Perindopril", "Captopril", "Losartan", "Telmisartan", "Valsartan",
               "Olmesartan", "Irbesartan", "Candesartan"], "factor": "pregnancy", "level": "Avoid",
     "text": "Boxed warning for fetal toxicity. Stop as soon as pregnancy is detected.", **label("Lisinopril")},
    {"drugs": ["Doxycycline", "Minocycline", "Tetracycline"], "factor": "pregnancy", "level": "Avoid",
     "text": "Can permanently discolour the developing teeth of the baby and affect bone growth. Avoid in pregnancy.", **label("Doxycycline")},
    {"drugs": ["Ibuprofen", "Diclofenac", "Naproxen", "Ketorolac", "Celecoxib", "Etoricoxib", "Aceclofenac"],
     "factor": "pregnancy", "level": "Use with caution",
     "text": "Avoid from 20 weeks of pregnancy: can cause low amniotic fluid and fetal kidney problems.",
     "source": "US FDA drug safety communication on NSAIDs in pregnancy (2020)",
     "url": "https://www.fda.gov/drugs/drug-safety-and-availability/fda-recommends-avoiding-use-nsaids-pregnancy-20-weeks-or-later-because-they-can-result-low-amniotic"},
    {"drugs": ["Acetylsalicylic acid"], "factor": "age", "at_least": 70, "level": "Use with caution",
     "text": "Avoid starting aspirin for primary prevention of heart disease in older adults; bleeding risk outweighs the benefit.",
     **BEERS},
    {"drugs": ["Digoxin"], "factor": "age", "at_least": 65, "level": "Use with caution",
     "text": "Avoid doses above 0.125 mg a day for atrial fibrillation or heart failure; toxicity is more likely.", **BEERS},
]


def main() -> None:
    vocabulary = set(json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8")))
    missing = sorted({d for rule in RULES for d in rule["drugs"] if d not in vocabulary})
    if missing:
        raise SystemExit(f"Not in the vocabulary: {missing}")
    OUTPUT.write_text(json.dumps({"rules": RULES, "note": "Decision-support cautions from published guidance; "
                                  "not yet reviewed by a clinician."}, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"PASS: {len(RULES)} rules covering {len({d for r in RULES for d in r['drugs']})} medicines -> {OUTPUT}")


if __name__ == "__main__":
    main()
