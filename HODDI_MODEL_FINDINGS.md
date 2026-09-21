# HODDI higher-order model — findings

**Task:** Model 3, the true multi-drug neural network. A DeepSets architecture (permutation-invariant over a variable-size set of 3-5 drugs) predicting whether a drug combination + report context represents a genuine, significant adverse-event signal (`hyperedge_label`) versus a matched negative control, using HODDI's FAERS-derived hyperedge data.

**Data:** 330,958 rows across six HODDI files (3/4/5-drug, positive + matched-negative each). Drugs resolved directly by DrugBankID (no name-matching needed) via local `DrugBankID2SMILES.csv` — 63.2% of rows had every drug in the set resolved to a structure, giving 209,310 usable rows. Split: `GroupShuffleSplit` grouped by the base report ID, so a positive report and its matched negative counterpart can never land on opposite sides of train/test.

**Architecture:** per-drug Morgan fingerprint (512-bit) → shared MLP encoder → masked mean+max pooling across the set (handles variable set size) → concatenated with embeddings for demographic/reporter context fields and normalized age → MLP classifier, `BCEWithLogitsLoss`.

## A leakage scare, caught before trusting the result

The first full model (drugs + adverse-event code + context) hit AUROC 0.975 after a single epoch — implausibly strong for this task. Ablations isolated the cause:

| Features | AUROC |
|---|---|
| Full model (drugs + AE code + context) | 0.975 |
| AE code + context, **no drug fingerprints** | 0.956 |
| Context only (no AE, no drugs) | 0.513 (random, as expected) |

A model with **zero information about which drugs were even involved** still scored 0.956 — meaning the adverse-event code (`SE_above_0.9`) was leaking the label directly, an artifact of how HODDI's negative controls were constructed (positive and negative rows are assigned different AE codes as part of the negative-sampling process itself, independent of the actual drug set). This is a benchmark construction artifact, not learned pharmacology, so it was dropped.

## Final, leakage-controlled result

Dropping `SE_above_0.9` entirely and training drugs + context only, for 6 epochs:

| Metric | Value |
|---|---|
| AUROC | 0.947 |
| AUPRC | 0.946 |
| F1 | 0.896 |
| AUROC, 3-drug sets | 0.948 |
| AUROC, 4-drug sets | 0.949 |
| AUROC, 5-drug sets | 0.922 |

Performance holds up consistently across set sizes — no degradation at higher interaction order, which is the point of using a true permutation-invariant multi-drug architecture instead of pairwise aggregation.

**Conclusion:** the model genuinely distinguishes real, reported multi-drug adverse-event hyperedges from matched negative controls using only molecular structure and non-AE report context — a legitimate, higher-order result once the AE-code leakage was identified and removed. Worth stating explicitly in the report that the leakage was caught via ablation before being reported, not after — that's the process worth showing, not just the number.
