# Patient clinical-feature dataset research

Research into a free, no-credentialing dataset for the diagram's "Patient Clinical Features"
branch (age/kidney/liver function/comorbidities). Not integrated into Model 4 — see
[MODEL4_GNN_FINDINGS.md](MODEL4_GNN_FINDINGS.md) for why that branch is out of scope for a
trained model (no dataset anywhere has real patient-drug-pair interaction outcomes).

## Candidate assessment

| Dataset | Relevant fields | Size/type | Access friction | License and suitability |
|---|---|---|---|---|
| **Synthea** — [project/downloads](https://synthetichealth.github.io/synthea/), [source](https://github.com/synthetichealth/synthea) | `patients.csv`: birth date/age, gender. `conditions.csv`: longitudinal SNOMED-coded diagnoses and comorbidities. `observations.csv`: LOINC-coded labs, including creatinine-based eGFR; other modules can produce renal/metabolic labs. Medications and encounters are also available. Liver-test coverage should be checked for the chosen modules and supplemented with an explicitly documented custom module if needed. | Fully synthetic; downloadable sample of 1,000+ patients or generate an unlimited seeded population. | None for sample download. Local generation requires Java 17+, but CSV output is straightforward. | Generator is Apache-2.0. The maintainers state generated records are free of cost, privacy, and security restrictions; retain attribution/NOTICE and check terminology licenses if redistributing coded data. Excellent for a public demo. |
| **eICU-CRD Demo 2.0.1** — [PhysioNet](https://physionet.org/content/eicu-crd-demo/2.0.1/) | `patient`: age, gender. `admissionDx`/`diagnosis`: diagnoses. `pastHistory`: comorbidities. `lab`: named laboratory results, including commonly recorded creatinine, bilirubin, ALT/AST and related chemistry values. Also medications and severity variables. | Real, de-identified ICU data; **2,500+ unit stays** from 20 hospitals. | Open direct ZIP/CSV/SQLite download; no CITI credentialing for the demo. Must follow the license. | Open Database License 1.0 (ODbL): academic use and redistribution are allowed subject to attribution, share-alike requirements for derivative databases, and keeping the database open. Strongest small real-data option. |
| **MIMIC-IV Demo 2.2** — [PhysioNet](https://physionet.org/content/mimic-iv-demo/2.2/) | `patients`: `gender`, `anchor_age`. `diagnoses_icd` plus `d_icd_diagnoses`: diagnoses/comorbidities. `labevents` plus `d_labitems`: numerical labs such as creatinine, total bilirubin, ALT and AST. Admissions and prescriptions are also present. | Real, de-identified hospital/ICU EHR subset; **100 patients**, 15.5 MB uncompressed. | Direct open download; no credentialing or CITI for the demo. | ODbL 1.0, with attribution/share-alike obligations. Legally usable, but 100 patients is too small for credible MLP training; best for schema development or screenshots. |
| **UCI Chronic Kidney Disease** — [UCI source](https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease) | Age; serum creatinine, blood urea, sodium, potassium, albumin and hematology; hypertension, diabetes, coronary artery disease, anemia, edema; CKD/non-CKD label. **No sex/gender and no liver panel.** | Real clinical records; **400 rows**. | Immediate download; no account, DUA or credentialing. | CC BY 4.0: redistribution and adaptation permitted with attribution. Useful renal supplement or baseline, but incomplete for the proposed full feature branch. |
| **UCI ILPD** — [UCI source](https://archive.ics.uci.edu/dataset/225/ilpd+indian+liver+patient+dataset) | Age, gender; total/direct bilirubin, alkaline phosphatase, ALT/SGPT, AST/SGOT, total protein, albumin and albumin/globulin ratio; liver-disease label. **No kidney markers and essentially no comorbidity history.** | Real patient records; **583 rows**. | Immediate download; no account, DUA or credentialing. | CC BY 4.0. Very convenient liver-function supplement, but not a complete patient-context dataset. |
| **UCI Diabetes 130-US Hospitals** — [UCI source](https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008) | Age bands, gender, up to three ICD diagnoses, diabetes medications, utilization history, HbA1c result, number of diagnoses/medications and readmission label. **It does not provide numerical creatinine, eGFR, ALT, AST or bilirubin.** | Real hospital encounters; **101,766 rows**, 47 features. | Immediate download; no account, DUA or credentialing. | CC BY 4.0. Large and easy, but a poor fit for kidney/liver modifiers. |
| **Kaggle liver/kidney mirrors** | Usually copies or cleaned versions of ILPD/CKD, with the same fields. | Varies. | Usually requires a Kaggle account/API acceptance. | License and provenance vary by uploader. Prefer the original UCI versions, whose provenance and CC BY 4.0 terms are explicit. |

## Top recommendation: Synthea

Use **Synthea as PolyGuard’s primary patient-feature dataset**, generating a reproducible population of roughly 5,000–20,000 patients with a fixed seed and CSV output.

It best meets the actual project constraints:

- usable immediately with no IRB, account, CITI course or DUA;
- safe to include with a public student demo;
- enough patients for an MLP and SHAP interface;
- internally linked demographics, diagnoses, comorbidities, observations and medications;
- population size and disease mix can be controlled.

Its important limitation is that these are **simulation-derived records, not clinical evidence that patient factors changed the outcome of a particular DDI**. PolyGuard therefore should not present the MLP as clinically validated or train it to “discover” DDI severity unless it has genuine patient–drug-pair outcome labels.

A defensible integration is:

```text
Synthea patient features
    → age/sex + renal/liver category + multi-hot comorbidities
    → small patient encoder
DrugBank/TWOSIDES/Hetionet/KEGG drug-pair embedding
    → concatenate with patient embedding
    → demonstrational context-adjustment layer
    → base DDI severity + transparent risk modifiers
```

Use patient records as selectable clinical profiles and apply documented modifiers—such as renal impairment, hepatic impairment, advanced age and relevant comorbidities—to PolyGuard’s existing drug-pair score. SHAP can then explain the **model’s contextual adjustment**, but the UI and report should label it “prototype decision support” or “simulated personalized risk,” not a validated prediction of patient harm. For a real-data sanity check, test the same preprocessing pipeline on the **eICU demo**, without redistributing it inside PolyGuard unless the ODbL obligations are deliberately handled.