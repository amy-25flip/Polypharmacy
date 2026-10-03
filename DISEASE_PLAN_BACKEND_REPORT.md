# Disease-plan backend report

## Built

- Added a reproducible Hetionet + curated disease formulary, with source strings on every medicine and stable slugs for disease IDs. The build excludes Hetionet diseases with fewer than three checkable medicines and keeps curated conditions even when their lists are shorter. All output medicine names are exact members of the application vocabulary.
- Added `GET /api/diseases`, `GET /api/diseases/{disease_id}/medicines`, and `POST /api/screen-candidates`. Searches use names and aliases; screening deduplicates case-insensitively, reports unknown entries, excludes self-comparisons, and summarizes selected medicines separately.
- The screening path batches Model 1 inference for uncached pairs, uses the exact documented-pairs index for provenance, caches normalized pairs in process, reuses Evidence Passport selective prediction and the chemistry disagreement rule, and ranks overlapping per-drug side-effect names using the explainability specificity weights.
- The formulary is optional at startup. A missing or corrupt file leaves existing routes available and makes all three new routes return HTTP 503.

## Data provenance and coverage

- Application vocabulary: 1,902 names; DrugBank ID mapping: 1,531 names.
- Hetionet: `Datasets/edges.sif` CtD and CpD edges, with names from `Datasets/hetionet-v1.0-nodes.tsv`. Of 91 disease nodes with these edges, 71 have at least three medicines that map through DrugBank IDs into the app vocabulary.
- Curated additions: 25 condition entries from the hand-curated input, with 96 source-to-medicine additions processed before deduplication. The final formulary has 83 diseases; 71 have Hetionet provenance and 25 have curated provenance. Overlap is expected.
- `CtD` means compound treats disease; `CpD` means compound palliates disease. These graph edges describe associations, not patient-specific prescribing guidance.

## Final disease list

| Disease | Medicines |
|---|---:|
| Acquired immunodeficiency syndrome | 14 |
| Alcohol dependence | 5 |
| Allergic rhinitis | 18 |
| Alzheimer's disease | 9 |
| Anaemia of chronic kidney disease | 2 |
| Ankylosing spondylitis | 15 |
| Asthma | 34 |
| Atherosclerosis | 6 |
| Atopic dermatitis | 13 |
| Atrial fibrillation | 5 |
| Attention deficit hyperactivity disorder | 13 |
| Autistic disorder | 8 |
| Benign prostatic hyperplasia | 3 |
| Bipolar disorder | 20 |
| Bone cancer | 5 |
| Brain cancer | 11 |
| Breast cancer | 39 |
| Chronic kidney disease | 13 |
| Chronic obstructive pulmonary disease | 17 |
| Colon cancer | 9 |
| Conduct disorder | 3 |
| Coronary artery disease | 39 |
| Crohn's disease | 8 |
| Depression | 3 |
| Dilated cardiomyopathy | 5 |
| Dyslipidaemia | 2 |
| Endogenous depression | 15 |
| Epilepsy | 25 |
| Esophageal cancer | 6 |
| Gastro-oesophageal reflux disease and peptic ulcer | 3 |
| Germ cell cancer | 7 |
| Gilles de la Tourette syndrome | 9 |
| Glaucoma | 12 |
| Gout | 11 |
| Head and neck cancer | 5 |
| Heart failure | 7 |
| Hematologic cancer | 52 |
| Hepatitis B | 3 |
| Hyperkalaemia in chronic kidney disease | 1 |
| Hypertension | 69 |
| Hyperthyroidism | 2 |
| Hypothyroidism | 4 |
| Kidney cancer | 19 |
| Leprosy | 3 |
| Liver cancer | 3 |
| Lung cancer | 17 |
| Lymphatic system cancer | 9 |
| Malaria | 14 |
| Melanoma | 7 |
| Migraine | 30 |
| Multiple sclerosis | 32 |
| Muscle cancer | 6 |
| Narcolepsy | 3 |
| Obesity | 10 |
| Osteoarthritis | 25 |
| Osteoporosis | 14 |
| Ovarian cancer | 10 |
| Pancreatic cancer | 10 |
| Panic disorder | 18 |
| Parkinson's disease | 26 |
| Peripheral nervous system neoplasm | 11 |
| Polycystic ovary syndrome | 4 |
| Primary biliary cirrhosis | 3 |
| Prostate cancer | 26 |
| Psoriasis | 15 |
| Psoriatic arthritis | 8 |
| Restless legs syndrome | 8 |
| Rheumatoid arthritis | 31 |
| Sarcoma | 8 |
| Schizophrenia | 27 |
| Secondary hyperparathyroidism in chronic kidney disease | 3 |
| Skin cancer | 8 |
| Stomach cancer | 9 |
| Systemic lupus erythematosus | 20 |
| Systemic scleroderma | 24 |
| Testicular cancer | 11 |
| Thyroid cancer | 4 |
| Tuberculosis | 4 |
| Type 2 diabetes mellitus | 24 |
| Ulcerative colitis | 16 |
| Urinary bladder cancer | 11 |
| Urinary tract infection | 2 |
| Uterine cancer | 7 |

## Curated sources used

- [ESC 2023: heart failure medicines](https://www.escardio.org/static-file/Escardio/Guidelines/Documents/ESC-heart-failure-patient-guidelines-update-2023.pdf)
- [ESC 2024: chronic coronary syndromes](https://www.escardio.org/guidelines/clinical-practice-guidelines/all-esc-practice-guidelines/chronic-coronary-syndromes/)
- [GINA 2025: asthma summary guide](https://ginasthma.org/wp-content/uploads/2025/06/GINA-Summary-Guide-2025-WEB_FINAL-WMS.pdf)
- [GOLD 2026: stable COPD bronchodilators](https://goldcopd.org/wp-content/uploads/2026/01/GOLD-REPORT-2026-v1.3-8Dec2025_WMV2.pdf)
- [India MoHFW: standard treatment guideline for hypertension](https://clinicalestablishments.mohfw.gov.in/sites/default/files/standard-treatment-guidelines/6591.pdf)
- [KDIGO 2017: CKD mineral and bone disorder](https://kdigo.org/guidelines/ckd-mbd/)
- [KDIGO 2024: CKD management, chapter 3](https://kdigo.org/guidelines/ckd-evaluation-and-management/)
- [KDIGO 2026: anemia in CKD](https://kdigo.org/guidelines/anemia-in-ckd/)
- [NICE CG184: reflux and peptic ulcer](https://www.nice.org.uk/guidance/cg184/chapter/Recommendations)
- [NICE CG91: depression with chronic physical illness](https://www.nice.org.uk/guidance/cg91/chapter/Recommendations)
- [NICE CG97: lower urinary tract symptoms and prostate enlargement](https://www.nice.org.uk/guidance/cg97/chapter/recommendations)
- [NICE NG100: rheumatoid arthritis](https://www.nice.org.uk/guidance/ng100/chapter/Recommendations)
- [NICE NG109: lower urinary tract infection](https://www.nice.org.uk/guidance/ng109/chapter/Recommendations)
- [NICE NG145 evidence review J: methimazole and propylthiouracil](https://www.nice.org.uk/guidance/ng145/evidence/j-management-of-thyrotoxicosis-anti-thyroid-drugs-pdf-250827180372)
- [NICE NG145: thyroid disease](https://www.nice.org.uk/guidance/NG145/chapter/recommendations)
- [NICE NG196: atrial fibrillation](https://www.nice.org.uk/guidance/ng196/chapter/Recommendations)
- [NICE NG203: CKD and hyperkalaemia](https://www.nice.org.uk/guidance/ng203/chapter/Recommendations)
- [NICE NG217: epilepsy](https://www.nice.org.uk/guidance/ng217/chapter/5-Treating-epileptic-seizures-in-children-young-people-and-adults)
- [NICE NG219: gout](https://www.nice.org.uk/guidance/ng219/chapter/Recommendations)
- [NICE NG222: depression](https://www.nice.org.uk/guidance/ng222/chapter/Recommendations)
- [NICE NG226: osteoarthritis](https://www.nice.org.uk/guidance/NG226/chapter/recommendations)
- [NICE NG238: lipid modification](https://www.nice.org.uk/guidance/ng238/chapter/recommendations)
- [NICE QS149: osteoporosis medicines](https://www.nice.org.uk/guidance/qs149/chapter/quality-statement-2-starting-drug-treatment)
- [NLEM 2022: section 18.3, medicines used in diabetes mellitus](https://www.mohfw.gov.in/sites/default/files/Notification%20and%20Report%20on%20National%20List%20of%20Essential%20Medicines%2C%202022.pdf)
- [NLEM 2022: section 24.1, antiasthmatic medicines](https://www.mohfw.gov.in/sites/default/files/Notification%20and%20Report%20on%20National%20List%20of%20Essential%20Medicines%2C%202022.pdf)
- [WHO 2022: drug-susceptible tuberculosis](https://www.who.int/publications/i/item/9789240048126)
- [WHO 2026: malaria guidelines](https://www.who.int/publications/i/item/guidelines-for-malaria/)
- [WHO EML 2025: section 18.5, medicines for diabetes](https://iris.who.int/bitstream/handle/10665/382243/B09474-eng.pdf)
- [WHO PEN 2020: type 2 diabetes management](https://iris.who.int/bitstream/handle/10665/334186/9789240009226-eng.pdf?sequence=1)

## Skipped for review

- Gliclazide: not present in the 1,902-name application vocabulary.
- Carbimazole: not present in the vocabulary; methimazole is retained only with its own evidence.
- Rifampin: US name absent from vocabulary; exact vocabulary name Rifampicin is used.
- Budesonide/formoterol fixed combination: no exact combination entry in vocabulary; the fixed combination is not represented as equivalent to either component.
- Sacubitril/valsartan fixed combination: no exact combination entry in vocabulary; not split into components for the heart failure formulary.
- Amoxicillin and ciprofloxacin for unspecified UTI: site, resistance, and patient factors are needed; omitted from broad reference list.

## Verification

Tested with a separate Uvicorn process on `127.0.0.1:8790`; the live port 8765 process was left alone. Full output from `python scripts/verify_disease_plan.py`:

```text
PASS diseases: 83 total; diabetes and kidney searches resolve
PASS formulary: all 83 disease medicine lists use vocabulary names with sources; unknown ID is 404
PASS parity: 20/20 pairs (10 documented, 10 undocumented) match /api/check severity and provenance
PASS self-comparison, case-insensitive deduplication, unmatched reporting, and adverse-effect basis
PASS >100-name validation: selected and candidates both return 422
PASS old endpoints: health unchanged; Warfarin + Amiodarone is Major
PASS warm timing: 70 candidates x 10 selected = 0.033s (<1.5s)
ALL VERIFICATIONS PASSED
```

- A fresh 100 candidates ? 15 selected request returned 1,500 candidate flags in **0.194 s** (HTTP 200). Timing is local and machine-specific.
- A separate `import main` / FastAPI TestClient probe was run with the formulary temporarily missing and then corrupt. In both cases import succeeded, `/api/health` returned 200, and all three new routes returned 503. The original file was restored.
- `python -m compileall` completed successfully for the changed Python modules and scripts.

## Deployment and file tracking

- `.gitignore` has explicit negations for `processed/disease_formulary.json` and `processed/disease_formulary_summary.md`, following the existing negations for the two Indian brand-name artifacts.
- The hard rule prohibited git commands. I inspected `.git/index` read-only instead of running `git ls-files processed`. It currently records these `processed/` paths:

```text
processed/conformal/eval.json
processed/conformal/quantiles.json
processed/disagreement_sentinel/disagreement_calibration.json
processed/disagreement_sentinel/fingerprint_cache.json
processed/disagreement_sentinel/model2_chemistry_pipeline.joblib
processed/documented_pairs.json
processed/drug_name_to_drugbank_id.json
processed/drug_vocabulary.json
processed/evidence_passport/calibration_bins.json
processed/evidence_passport/drug_support_counts.json
processed/evidence_passport/risk_coverage.json
processed/evidence_passport/support_tiers.json
processed/evidence_passport/thresholds.json
processed/explainability_data.json
processed/hoddi_deepsets_final_model.pt
processed/hoddi_vocabs.json
processed/indian_brand_names.json
processed/indian_brand_names_summary.md
processed/model1_severity_pipeline.joblib
```

- The new formulary files are present on disk and allowed by `.gitignore`; the index inspection does not establish whether they have been staged or committed. No git command or staging operation was run.

## Limitations and uncertainty

- This is a medicine-browsing reference for a clinician. It does not account for diagnosis subtype, dose, route, duration, age, kidney function, pregnancy, allergies, culture results, or local resistance. No medicine is labelled preferred or first-line.
- A documented pair means an exact pair appears in the DDInter-derived index. As in `/api/check`, severity still comes from Model 1; it is not retrieved as a proven patient-specific clinical label. An undocumented pair is model extrapolation and requires independent review.
- `adverse_effects` are names present in both drugs' individual Hetionet side-effect profiles. They are plausible additive concerns, not observed outcomes or pair-specific adverse-event records. Missing DrugBank IDs or side-effect data yield an empty list.
- `uncertain` follows the Evidence Passport abstention/Low reliability test and the high chemistry-model disagreement override for eligible undocumented pairs. It does not remove the severity label.
- Hetionet and guideline coverage is incomplete. Some condition lists are short because the vocabulary lacks a named medicine or because a fixed combination has no exact vocabulary entry. The six review exclusions above are intentional.
