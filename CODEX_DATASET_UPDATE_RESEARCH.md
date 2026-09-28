# Current dataset landscape for PolyGuard

Research checked through **September 28, 2026**.

## Overall priority

The upgrades worth considering, in order:

1. **Upgrade DDInter to DDInter 2.0.** This is the clearest, easiest, and most defensible improvement: 28% more DDI records, more drugs, updated severity/mechanism annotations, and public CSV downloads.
2. **Add PrimeKG—or, if you have time to experiment, OptimusKG—as a supplementary graph.** PrimeKG is substantially richer than Hetionet for drug-centric work. OptimusKG is its new 2026 successor, but it is much larger and less mature.
3. **Keep HODDI exactly as it is.** Your files appear to be the current 2025 release; no official successor was found.
4. **Keep TWOSIDES for benchmark comparability.** There is no official TWOSIDES v2. HODDI is effectively your modern FAERS-derived complement.
5. **Do not urgently refresh DrugBank.** The latest export is newer, but academic bulk downloads are temporarily unavailable and the schema has not meaningfully changed since 2023–2024.
6. **Do not attempt a new FAERS or Indian pharmacovigilance build immediately before review.** It would be a separate data-engineering and signal-validation project, not a simple dataset addition.

A pragmatic pre-review plan would therefore be: **DDInter 2.0 now; optionally demonstrate a small PrimeKG comparison; document everything else as future work.**

---

## 1. DrugBank

### Finding

The current downloadable DrugBank release is **5.1.22, dated June 27, 2026**. However, DrugBank currently says that **all academic dataset downloads are temporarily paused** while it changes its distribution program. Eligible academic use remains described as free/noncommercial under an academic licence, but a new student cannot presently retrieve the full export normally. [DrugBank 5.1.22 release page](https://go.drugbank.com/releases/latest)

There has not been a meaningful public XML-schema transition since a typical 2023–2024 export:

- 5.1.10: January 4, 2023
- 5.1.11: January 3, 2024
- 5.1.12: March 14, 2024
- 5.1.13: January 2, 2025
- 5.1.14–5.1.22: releases during 2026

DrugBank’s official notes mark all of those as having **“no significant changes.”** The XML schema remains version 5.1, and the traditional interaction element still contains the other drug’s ID, name and free-text description. DrugBank also documents a richer structured-interaction representation with subject/affected drug, severity, action and extended description, but its availability depends on the particular licensed export or product. [Release notes](https://go.drugbank.com/release_notes), [XML format reference](https://docs.drugbank.com/xml/)

The growing export size—from about 219 MB in 5.1.10 to 286 MB across the latest release package—shows continuing content additions, but not a format break. [DrugBank release history](https://go.drugbank.com/releases)

A separate issue is that your `DrugBank.csv` does **not** sound like an official raw export. The `Drug1_ID`, SMILES pair and binary `Y` layout is probably a paper-specific or repository-specific ML derivative. Consequently:

- Its DrugBank source version cannot be established from the file date.
- `Y=0` may mean artificially sampled negative, not a clinically verified absence of interaction.
- Refreshing from raw DrugBank would require reproducing the unknown pair construction and negative-sampling procedure.
- Mixing old and new pairs could introduce duplicates or train/test leakage.

### Availability

- Latest academic XML/SDF snapshot: normally academic-licence access, but **bulk academic downloads are currently paused**.
- Commercial/API and curated clinical products: paid or institution-dependent.
- Public mirrors of full DrugBank data: should not be assumed lawful or licence-compatible.
- Existing derived CSV: usable only under the licence attached to its original source, if known.

### Honest recommendation

**Do not make this a pre-review migration.** Retain the current derived dataset, explicitly label its version as “unknown/provenance unresolved,” and avoid claiming it represents current DrugBank.

Register for notice when academic downloads reopen. Later, obtain 5.1.22 or its successor and regenerate the entire pair dataset reproducibly—not by appending rows to the present CSV. If structured severity/action information is accessible under your academic licence, that would be more valuable than merely refreshing SMILES.

**Priority: low before review; medium for the next reproducibility pass.**

---

## 2. DDInter

### Finding

There is a meaningfully newer release: **DDInter 2.0**, whose site reports a last update of **May 14, 2024**. The associated database paper was published in the 2025 Nucleic Acids Research database issue.

Compared with DDInter 1.0:

| Measure | DDInter 1.0 | DDInter 2.0 | Change |
|---|---:|---:|---:|
| DDI records | 236,834 | 302,516 | +27.7% |
| Drug entries | 1,972 | 2,310 | +17% |
| Major interactions | 39,480 | 52,943 | +34% |
| Moderate interactions | 145,132 | 195,776 | +35% |
| Minor interactions | 9,805 | 12,522 | +28% |

DDInter 2.0 also provides:

- 8,398 distinct mechanism/management descriptions
- 8,359 drug–disease interactions
- 857 drug–food interactions
- 6,033 therapeutic-duplication records
- updated ATC mappings and ADMET-related information

The paper explicitly describes the 302,516 DDI total as a 27.73% expansion over the first release. [DDInter 2.0 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11701621/), [current statistics](https://ddinter2.scbdd.com/statistics/)

This means a file assembled from the original DDInter—not merely downloaded in 2026—is now materially outdated.

### Availability

DDInter 2.0 is open-access, and its download page provides CSVs divided by ATC category. You will need to concatenate and deduplicate them carefully because a pair may be present in more than one category when its drugs span classifications. [Official download page](https://ddinter2.scbdd.com/download/)

The publication is under a CC BY-NC licence; check the download-site terms when redistributing processed data.

### Honest recommendation

**Upgrade this one.** It delivers a defensible coverage improvement without requiring you to invent labels from noisy raw reports.

For the capstone, keep the original snapshot frozen for baseline reproduction and create a clearly named DDInter 2.0 dataset. Compare:

- unique unordered pairs;
- unique drugs;
- severity distribution;
- overlap with your present four-disease subset;
- whether the disease filter was based on drug indication, ATC class, or some other rule.

Do not blindly replace the four-disease subset until that filtering rule is reproduced.

**Priority: highest. Worth doing before review.**

---

## 3. TWOSIDES

### Finding

I found **no official TWOSIDES 2.0 or actively maintained direct successor**. The Tatonetti Lab still distributes the original resource and describes TWOSIDES as its comprehensive drug–drug–effect dataset. The original download contains approximately 3.78 million statistically significant drug-pair/side-effect associations. [Tatonetti Lab TWOSIDES page](https://tatonettilab.org/resources/tatonetti-stm.html)

The frequently used ML version remains the Decagon-style derivative:

- 645 drugs
- 963 polypharmacy side-effect types
- approximately 4.58 million positive triplets

Recent DDI papers continue to reuse this derivative rather than a newly refreshed TWOSIDES release. [Example current TWOSIDES packaging](https://github.com/jcsun-00/Twosides)

That matters because TWOSIDES is best treated as a **historical benchmark**, not current ground truth. It was mined from old spontaneous reports and inherits confounding, reporting bias, duplicate-report issues and the inability of spontaneous-report association alone to prove causality.

The practical modern alternatives are not drop-in replacements:

- **Raw FAERS** is updated quarterly and covers January 2004 onward. It is public-domain/CC0, but recreating pairwise safety signals requires deduplication, drug-name normalization, indication/confounding controls and a declared statistical procedure. [FDA FAERS](https://www.fda.gov/drugs/drug-approvals-and-databases/fda-adverse-event-reporting-system-faers-database)
- **HODDI** uses FAERS from 2014Q3–2024Q3 and captures higher-order combinations. It complements TWOSIDES but is not directly equivalent.
- **SIDER** remains a single-drug label-derived adverse-effect resource, not a DDI replacement; its current public release is still 4.1 from 2015. [SIDER](https://sideeffects.embl.de/)

### Availability

- TWOSIDES: publicly downloadable.
- Raw FAERS: public, quarterly and legally straightforward.
- A modern TWOSIDES-equivalent created from current FAERS: no authoritative, widely adopted, ready-made public successor was found.
- Community Kaggle/Hugging Face FAERS conversions exist, but provenance and cleaning quality vary substantially.

### Honest recommendation

**Keep TWOSIDES for benchmark comparability; do not represent it as current clinical evidence.** Pair it conceptually with HODDI: TWOSIDES supplies the established pairwise benchmark and HODDI supplies recent higher-order data.

Do not try to rebuild TWOSIDES from current FAERS immediately before review. A small, time-bounded FAERS validation—such as checking several high-risk predicted pairs in recent quarters—could make a good future-work or demo component, but it should not become the primary training dataset without much more validation.

**Priority: no replacement needed.**

---

## 4. Hetionet, PrimeKG and newer biomedical knowledge graphs

### Finding

Hetionet remains a respected, reproducible benchmark, but it is no longer the richest default graph for a new drug-centric project. Its original sources are old: for example, its drug layer traces to DrugBank 4.2-era approved small molecules, giving roughly 1,550 drug compounds.

**PrimeKG** is considerably richer:

- 129,375 nodes
- 10 entity types
- 4,050,249 stored relationships, or about 8.1 million when reverse edges are counted
- approximately 7,957 drugs
- more than 17,000 grouped diseases
- drug–drug, drug–protein, protein–protein, indication, contraindication, off-label, phenotype and side-effect relationships

It integrates 20 source resources and performs identifier harmonization upstream. [PrimeKG paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9893183/), [PrimeKG repository](https://github.com/mims-harvard/PrimeKG)

PrimeKG is therefore meaningfully richer than Hetionet for:

- drug-feature construction;
- cold-start drug representations;
- drug–protein and disease-context features;
- multi-hop explanations;
- contraindication-aware analysis.

It is not necessarily a better label source. Its approximately 2.67 million directed drug–drug edges originate largely from DrugBank and are typed broadly as `drug_drug`; they do not reproduce DDInter’s severity taxonomy. Also, adding both PrimeKG and DrugBank-derived DDI labels can cause circularity or target leakage.

There is now an even newer development: the PrimeKG repository states that **PrimeKG has been superseded by OptimusKG**. The 2026 OptimusKG release reports:

- 190,531 nodes
- 21,813,816 edges
- 27 relation types
- 65 resources grounded through 18 ontologies
- Parquet downloads and a Python client

It is publicly hosted through Harvard Dataverse, although individual upstream licences still apply. Its paper is currently described as under review. [OptimusKG repository](https://github.com/mims-harvard/optimuskg), [OptimusKG preprint](https://arxiv.org/abs/2604.27269)

There is also a very recent **PrimeKG-Plus** preprint/dataset, refreshed in 2026 and available on Zenodo. It reports refreshed DrugBank-derived DDI edges and expanded literature-derived content. It is promising, but too new to call an established standard. [PrimeKG-Plus repository](https://github.com/DSDD-UCPH/PrimeKG-Plus)

### Availability

- Hetionet: public.
- PrimeKG: direct CSV download from Harvard Dataverse; dataset catalogued as CC0.
- OptimusKG: public Python client/Parquet downloads, but component-specific upstream licensing must be respected.
- PrimeKG-Plus: public Zenodo/GitHub release, currently associated with a preprint.

### Honest recommendation

For a review happening soon:

- **Keep Hetionet as your reproducible baseline.**
- If you can afford one graph improvement, **add PrimeKG**, not replace Hetionet invisibly.
- Use only non-label relations when constructing features for DDI prediction. In particular, remove `drug_drug` edges and any path that directly encodes the evaluation label.
- Report the comparison as “Hetionet versus PrimeKG feature enrichment.”

OptimusKG is objectively newer and larger, but adopting a 21.8-million-edge graph immediately before review could consume substantial time in storage, mapping, leakage auditing and model retraining. It is an excellent **future-work target**, or a small exploratory experiment if your graph pipeline already supports Parquet and typed edges.

**Priority: PrimeKG medium-high; OptimusKG medium after review; full graph migration not urgent.**

---

## 5. HODDI

### Finding

Your HODDI files appear to come from the current official dataset introduced in **February 2025**. Its documented release contains:

- 109,744 balanced positive/negative records
- 2,506 unique drugs
- 4,569 side effects
- FAERS coverage from 2014Q3 through 2024Q3
- records and evaluation subsets for multi-drug combinations
- public code and datasets on GitHub

The paper explicitly positions HODDI as the first dataset focused on higher-order drug–side-effect associations. [HODDI paper](https://arxiv.org/abs/2502.06274)

I found no official HODDI 2.0, later FAERS-quarter extension, peer-reviewed successor release, or revised dataset superseding the files you described. The six `3_drug`, `4_drug` and `5_drug` positive/negative files match the evaluation-subset structure associated with the release.

One important caveat: HODDI’s negatives are generated through resampling rather than confirmed clinical non-interactions. Its paper shows that positive and negative examples have noticeably different side-effect-frequency distributions. That makes random-split performance potentially easier than real unseen-combination deployment.

Also, the dataset represents reported drug combinations associated with adverse events; it does not prove that a genuinely higher-order causal interaction occurred among every drug in a record.

### Availability

Public through the authors’ GitHub repository and paper. No special licence or partnership barrier was identified for academic experimentation.

### Honest recommendation

**Keep your present HODDI files. They are already current.** Spend available time improving evaluation rather than searching for a nonexistent update:

- group splits by drug combination or report period;
- test unseen-drug or unseen-combination generalization;
- state how negatives were generated;
- avoid describing every positive as a clinically established causal interaction;
- report HODDI separately from pairwise DDInter/DrugBank evaluation.

**Priority: no dataset refresh; high priority for leakage-resistant evaluation and documentation.**

---

## 6. New datasets and sources worth considering

### A. Current FAERS

FAERS remains the most important continuously updated open source. FDA releases it quarterly, and openFDA provides public-domain/CC0 access with a roughly three-month update lag. [openFDA FAERS description](https://open.fda.gov/data/faers/)

**Better/newer?** Yes in recency, not automatically in label quality.

**Obtainable?** Fully public.

**Recommendation:** Do not make it a new primary training dataset before review. A narrow temporal validation set—predictions checked against later FAERS quarters—is a worthwhile future experiment and is more scientifically interesting than simply appending millions of noisy reports.

### B. PK-DDIP / quantitative pharmacokinetic interactions

A 2025 project describes **3,779 manually verified, AUC-based pharmacokinetic interactions extracted from FDA DailyMed labels**, with 1,803 harmonized pairs across 639 overlapping drugs. Unlike binary pair datasets, this can encode direction and quantitative exposure change. The associated work is presently a preprint/tool rather than an established large benchmark. [PK-DDIP integration paper](https://arxiv.org/abs/2508.08351)

**Better/newer?** Meaningfully different and potentially useful for mechanism/explanation, but much smaller.

**Obtainable?** The paper and platform are public; verify that the complete table is downloadable under suitable terms before planning integration.

**Recommendation:** Attractive as a small external validation or explainability dataset after DDInter 2.0. Not a replacement for your main datasets.

### C. Literature-mined DDI corpora

The dedicated NLP benchmarks remain surprisingly old. DDIExtraction 2013 and the TAC DDI corpora are still commonly used even in 2025 work. A more recent **Translational Drug Interaction Corpus** adds annotations for evidence, certainty, polarity, study type, direction and mechanism, but it is an NLP corpus rather than a broad pairwise interaction database. [Translational DDI Corpus](https://pubmed.ncbi.nlm.nih.gov/35616099/)

DrugProt is newer and larger, but it covers chemical–protein relations rather than drug–drug interactions, so it would enrich mechanism features rather than supply DDI labels. [DrugProt overview](https://pmc.ncbi.nlm.nih.gov/articles/PMC10683943/)

**Better/newer?** Useful for an explanation or evidence-retrieval module, not better training labels for the current predictor.

**Obtainable?** Generally public for research.

**Recommendation:** Not worth adding before review unless literature-grounded explanations are already a core deliverable. DDInter 2.0 already provides curated mechanisms and citations with far less integration work.

### D. Indian/regional pharmacovigilance data

India’s Pharmacovigilance Programme, **PvPI**, collects individual case safety reports and forwards them to the WHO global system. Public PvPI pages provide reporting tools, forms, aggregate documents and programme information—not an open, analysis-ready dump of Indian patient-level adverse-event or DDI reports. [PvPI programme page](https://cdsco.gov.in/opencms/opencms/en/PvPI/index.html), [PvPI toolkit](https://www.ipc.gov.in/PvPI/toolkit.html)

The underlying systems include:

- **VigiFlow**, used by national centres for case management;
- **VigiSearch/VigiLyze**, available to participating national centres;
- **VigiBase**, the WHO global ICSR database, which is not an unrestricted public bulk download.

Therefore, an India-specific DDI dataset comparable to FAERS is not realistically downloadable by an ordinary student. Access would likely require collaboration with IPC/PvPI, a participating adverse-drug-reaction monitoring centre, WHO-UMC access, or a research agreement.

**Better/newer?** Potentially highly relevant, but not publicly obtainable in usable raw form.

**Obtainable?** Generally partnership-, institutional-access-, or request-dependent.

**Recommendation:** Do not promise an Indian pharmacovigilance training dataset. Instead, give PolyGuard an honest Indian-context layer by:

- evaluating coverage of drugs commonly marketed or prescribed in India;
- preserving Indian brand-to-generic mappings separately from pharmacological labels;
- including India-relevant comorbidities and polypharmacy scenarios in case studies;
- citing PvPI as a desired future validation partner;
- clearly distinguishing Indian market relevance from India-derived clinical evidence.

That is more credible than presenting US FAERS data as Indian clinical data.

---

# Final recommendation

For the capstone’s next review, I would make exactly one major data change: **migrate the DDInter component to DDInter 2.0 and document the before/after statistics**.

If time remains, run a contained **Hetionet-versus-PrimeKG feature comparison**, with direct DDI edges removed to prevent leakage. Leave DrugBank, TWOSIDES and HODDI frozen so your existing results remain reproducible.

The strongest honest narrative is:

> PolyGuard combines an established pairwise pharmacovigilance benchmark (TWOSIDES), current curated clinical interactions (DDInter 2.0), higher-order FAERS-derived combinations through 2024Q3 (HODDI), chemical features, and biomedical graph context. Historical resources are retained for benchmark comparability, while their age, spontaneous-report bias, synthetic-negative construction and non-Indian provenance are explicitly disclosed.

That is a more defensible capstone than hurriedly adding raw FAERS, a newly released 22-million-edge graph, or inaccessible PvPI data immediately before review.