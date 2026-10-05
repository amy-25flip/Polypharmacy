"""How many of the diagnoses doctors of each specialty search most often can PolyGuard find?

Run from any directory (server running): python scripts/coverage_check.py --base-url http://127.0.0.1:8765
Writes doctor_review/COVERAGE_ANALYSIS.md.

The diagnosis lists are a PLANNING estimate of high-frequency outpatient diagnoses per specialty. They
come from a literature scan (NSS 75th round ailment categories, an Indian multicentre skin OPD cohort,
institutional and pharmacy prescription studies); no national table of visits by specialty exists. Each
line is the phrase a doctor would type and the diagnosis it should find. Conditions that are mainly
procedural (hernia, cataract, fracture follow-up) are left out because there is no medicine list to show.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "doctor_review" / "COVERAGE_ANALYSIS.md"

H, T2, GERD = "Hypertension", "Type 2 diabetes mellitus", "Gastro-oesophageal reflux disease and peptic ulcer"
SPECIALTIES: dict[str, list[tuple[str, str]]] = {
    "General practice / primary care": [
        ("fever", "Undifferentiated fever"), ("cold", "Acute upper respiratory infection"), ("sore throat", "Acute pharyngitis and tonsillitis"),
        ("loose motions", "Acute gastroenteritis"), ("backache", "Low back pain"), ("hypertension", H), ("diabetes", T2),
        ("allergic rhinitis", "Allergic rhinitis"), ("asthma", "Asthma"), ("gerd", GERD), ("iron deficiency", "Iron-deficiency anaemia"),
        ("uti", "Urinary tract infection"), ("ringworm", "Dermatophytosis of skin"), ("scabies", "Scabies")],
    "General medicine": [
        ("hypertension", H), ("diabetes", T2), ("dyslipidaemia", "Dyslipidaemia"), ("coronary artery disease", "Coronary artery disease"),
        ("heart failure", "Heart failure"), ("chronic kidney disease", "Chronic kidney disease"), ("copd", "Chronic obstructive pulmonary disease"),
        ("pneumonia", "Community-acquired pneumonia"), ("fever", "Undifferentiated fever"), ("anaemia", "Iron-deficiency anaemia"),
        ("stroke", "Stroke, secondary prevention"), ("gout", "Gout"), ("hypothyroidism", "Hypothyroidism"), ("loose motions", "Acute gastroenteritis")],
    "Paediatrics": [
        ("cold", "Acute upper respiratory infection"), ("fever", "Undifferentiated fever"), ("sore throat", "Acute pharyngitis and tonsillitis"),
        ("ear infection", "Acute otitis media"), ("loose motions", "Acute gastroenteritis"), ("pneumonia", "Community-acquired pneumonia"),
        ("asthma", "Asthma"), ("allergic rhinitis", "Allergic rhinitis"), ("anaemia", "Iron-deficiency anaemia"), ("scabies", "Scabies"),
        ("impetigo", "Impetigo"), ("worms", "Helminthiasis"), ("dengue", "Dengue fever")],
    "Obstetrics and gynaecology": [
        ("vomiting in pregnancy", "Nausea and vomiting of pregnancy"), ("iron deficiency", "Iron-deficiency anaemia"),
        ("period pain", "Dysmenorrhoea"), ("heavy periods", "Abnormal uterine bleeding"), ("pcod", "Polycystic ovary syndrome"),
        ("vaginal thrush", "Vulvovaginal candidiasis"), ("pid", "Pelvic inflammatory disease"), ("uti", "Urinary tract infection"),
        ("fibroid", "Uterine fibroids"), ("endometriosis", "Endometriosis"), ("gestational diabetes", "Gestational diabetes"),
        ("pre-eclampsia", "Pre-eclampsia"), ("menopause", "Menopausal symptoms")],
    "General surgery": [
        ("piles", "Haemorrhoids"), ("anal fissure", "Anal fissure"), ("cellulitis", "Cellulitis"), ("boils", "Folliculitis and furunculosis"),
        ("gerd", GERD), ("constipation", "Constipation"), ("wound infection", "Postoperative wound infection"), ("uti", "Urinary tract infection")],
    "Orthopaedics": [
        ("backache", "Low back pain"), ("neck pain", "Neck pain and cervical spondylosis"), ("sprain", "Soft-tissue sprain or strain"),
        ("osteoarthritis", "Osteoarthritis"), ("osteoporosis", "Osteoporosis"), ("gout", "Gout"), ("rheumatoid arthritis", "Rheumatoid arthritis"),
        ("tendonitis", "Tendonitis"), ("ankylosing spondylitis", "Ankylosing spondylitis")],
    "Dermatology": [
        ("tinea", "Dermatophytosis of skin"), ("acne", "Acne vulgaris"), ("psoriasis", "Psoriasis"), ("eczema", "Atopic dermatitis"),
        ("contact dermatitis", "Allergic contact dermatitis"), ("dandruff", "Seborrhoeic dermatitis"), ("scabies", "Scabies"),
        ("urticaria", "Urticaria"), ("vitiligo", "Vitiligo"), ("melasma", "Melasma"), ("alopecia areata", "Alopecia areata"),
        ("impetigo", "Impetigo"), ("nail fungus", "Onychomycosis"), ("shingles", "Herpes zoster"), ("warts", "Viral warts")],
    "Psychiatry": [
        ("depression", "Depression"), ("schizophrenia", "Schizophrenia"), ("bipolar", "Bipolar disorder"), ("panic", "Panic disorder"),
        ("adhd", "Attention deficit hyperactivity disorder"), ("alcohol dependence", "Alcohol dependence"), ("anxiety", "Generalised anxiety disorder"),
        ("insomnia", "Insomnia disorder"), ("ocd", "Obsessive-compulsive disorder"), ("alzheimer", "Alzheimer's disease")],
    "ENT": [
        ("tonsillitis", "Acute pharyngitis and tonsillitis"), ("cold", "Acute upper respiratory infection"), ("ear infection", "Acute otitis media"),
        ("sinusitis", "Acute rhinosinusitis"), ("allergic rhinitis", "Allergic rhinitis"), ("ear canal infection", "Acute otitis externa"),
        ("vertigo", "Vertigo")],
    "Ophthalmology": [
        ("pink eye", "Conjunctivitis"), ("allergic conjunctivitis", "Allergic conjunctivitis"), ("dry eye", "Dry-eye disease"),
        ("blepharitis", "Blepharitis"), ("glaucoma", "Glaucoma"), ("uveitis", "Uveitis")],
    "Cardiology, pulmonology and endocrinology": [
        ("hypertension", H), ("coronary artery disease", "Coronary artery disease"), ("atrial fibrillation", "Atrial fibrillation"),
        ("heart failure", "Heart failure"), ("dyslipidaemia", "Dyslipidaemia"), ("asthma", "Asthma"), ("copd", "Chronic obstructive pulmonary disease"),
        ("diabetes", T2), ("hypothyroidism", "Hypothyroidism"), ("hyperthyroidism", "Hyperthyroidism"), ("obesity", "Obesity"),
        ("chronic kidney disease", "Chronic kidney disease")],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    base = parser.parse_args().base_url.rstrip("/")

    def finds(term: str, expected: str) -> bool:
        with urlopen(f"{base}/api/diseases?q={urllib.parse.quote(term)}", timeout=30) as response:
            return any(d["name"] == expected for d in json.load(response)["diseases"])

    total = found = 0
    rows, gaps = [], []
    for specialty, entries in SPECIALTIES.items():
        hits = [(term, name) for term, name in entries if finds(term, name)]
        misses = [name for term, name in entries if (term, name) not in hits]
        total += len(entries)
        found += len(hits)
        rows.append((specialty, len(hits), len(entries)))
        gaps += [(specialty, name) for name in misses]

    lines = ["# Coverage analysis: which common diagnoses can doctors find?", "",
             "Generated by `scripts/coverage_check.py` against the running app. This is a **planning estimate**, not a measurement.",
             "",
             "## What this does and does not show", "",
             "- Each specialty has a list of 6 to 15 diagnoses it is likely to search most often, taken from a literature scan of Indian outpatient "
             "studies (NSS 75th round ailment categories, an Indian multicentre skin OPD cohort, institutional OPD and pharmacy prescription studies).",
             "- **No national table of visits or doctors by specialty exists**, so no figure here is an all-India statistic, and nothing here proves the app reaches "
             "\"80% of doctors\". The honest test is a pilot: code the diagnoses on consecutive real prescriptions from several clinics and count how many the app finds.",
             "- A diagnosis counts as found when the phrase a doctor would type returns that diagnosis, and it has a medicine list. "
             "Mainly procedural conditions (hernia, cataract, fracture follow-up) are left out.", "",
             "## Result", "", "| Specialty | Found | Of | Share |", "|---|---:|---:|---:|"]
    for specialty, hit, count in rows:
        lines.append(f"| {specialty} | {hit} | {count} | {100 * hit // count}% |")
    lines += [f"| **All lists together** | **{found}** | **{total}** | **{100 * found // total}%** |", "",
              f"{sum(1 for _, h, c in rows if h / c >= 0.8)} of {len(rows)} specialty lists are at 80% or better.", "",
              "## Still missing", ""]
    lines += [f"- {specialty}: {name}" for specialty, name in gaps] or ["- None."]
    lines += ["", "The eye and ear conditions are left out on purpose for now. Their medicines are almost all drops, and the interaction data in the "
              "checker is for tablets and injections, so listing them would make a drop look like a tablet. They need route-specific data first.", ""]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{found}/{total} = {100 * found // total}%")
    for specialty, hit, count in rows:
        print(f"  {specialty}: {hit}/{count}")
    print("missing:", [name for _, name in gaps])


if __name__ == "__main__":
    main()
