# Indian brand-name mapping summary

## Scope

This file accompanies `indian_brand_names.json`, a curated index of **248** normalized Indian trade-name entries. Strength-qualified variants (for example, `dolo 650` and `augmentin 625`) are retained because that is often what is written on a prescription; they count as separate lookup keys. Every mapped value was mechanically checked against the 1,902 exact strings in `drug_vocabulary.json`.

Coverage includes analgesics and antipyretics; antibiotics and other anti-infectives; antidiabetics and insulins; antihypertensive, cardiac, antiplatelet and anticoagulant drugs; antacids, H2 blockers and proton-pump inhibitors; statins and other lipid drugs; antihistamines and respiratory drugs; systemic and inhaled corticosteroids; psychiatric, neurologic and CNS drugs; and common thyroid, vitamin/mineral, gastrointestinal, rheumatology, urology and erectile-dysfunction products.

## Combination handling

Combination brands map to every active ingredient that has an exact vocabulary entry, in clinically meaningful ingredient order where practical. Examples include Augmentin/Clavam (`Amoxicillin` + `Clavulanic acid`), Combiflam (`Ibuprofen` + `Acetaminophen`), Glycomet GP (`Metformin` + `Glimepiride`), Telma AM (`Telmisartan` + `Amlodipine`) and Foracort (`Budesonide` + `Formoterol`).

When the local vocabulary lacks one component, the entry deliberately retains only the component(s) that can be represented exactly. Examples are Deriphyllin (only `Theophylline`, because etofylline is absent), Zostum (only `Cefoperazone`, because sulbactam is absent), Cremaffin (only `Magnesium hydroxide`) and Syncapone (`Levodopa` + `Entacapone`, because carbidopa is absent). Multivitamin products similarly list only prominent ingredients present in the vocabulary. No near-synonym was substituted for a missing ingredient.

## Research basis

The starting set used established pharmacology knowledge and widely encountered Indian prescription brands, then cross-checked representative products and compositions against Indian medicine catalogues and published sources:

- [Apollo Pharmacy generic catalogue](https://www.apollopharmacy.in/shop-by-category/generic) exposes brand/composition pairs across hypertension, antibiotics, lipids and other categories (for example Amlip/amlodipine, Amoxyclav/amoxicillin-clavulanate, Floxip/ciprofloxacin and Lipvas/atorvastatin).
- [PharmEasy's medically reviewed generic-medicine guide](https://pharmeasy.in/blog/generic-medicine-list-in-india-a-guide-to-common-generic-medicines/) provides category and ingredient checks, including common combination ingredients.
- [CIMS India](https://www.mims.com/india/company) is an India-specific drug/company directory used as a secondary brand-market reference.
- [A peer-reviewed Indian study of Jan Aushadhi access and popular brands](https://pmc.ncbi.nlm.nih.gov/articles/PMC9107149/) supports the focus on common chronic-disease and essential medicines.
- [A peer-reviewed study of antibiotic brands in the Indian market](https://pmc.ncbi.nlm.nih.gov/articles/PMC8117914/) supports the antibiotic category and the need to distinguish combination formulations.

This is a pragmatic curated compatibility layer, not a regulatory drug dictionary. Brand ownership and formulations can vary by strength, suffix, dosage form, manufacturer and market; similarly named brands can even contain different ingredients. The index is therefore intentionally conservative, requires doctor review, does not imply interchangeability, and is not exhaustive of India's very large branded-generic market. Future work should use a licensed, versioned Indian product database with manufacturer, strength, dosage-form and regulatory identifiers.

## Verification record

- JSON parsed successfully; keys are lowercase, trimmed and whitespace-collapsed.
- All mapped generic values are exact members of `drug_vocabulary.json`.
- Frontend TypeScript check: passed (`npx tsc --noEmit -p tsconfig.app.json`, zero errors).
- Frontend test suite: passed (`npm test -- --run`, 7 files and 21 tests).
- Backend Python AST checks: passed for `brand_names.py`, `main.py` and `prescription_scan.py`.
- Full model-load smoke test: passed from `webapp`; all real models loaded, the brand-index status reported 225 names, startup reached `Ready`, and a live `Dolo 650` endpoint-function check returned `Acetaminophen` with `matched_via_brand: "dolo 650"`.
