# Chemistry features experiment — findings

**Hypothesis:** molecular structure (Morgan fingerprints) would generalize to unseen drugs better than the text baseline, which leans on drug-name lexical patterns.

**Method:** drug names resolved to SMILES via local Hetionet + DrugBank data (no external API needed) — 997/1,902 names (52.4%), covering 48,991/130,422 pairs (37.6%). Three models — text-only, chemistry-only (Morgan r2/1024-bit, pair ops: abs-diff/AND/OR/product/Tanimoto), and hybrid — trained/evaluated on the *identical* resolved-pair rows and identical standard/cold-start splits for a fair comparison.

**Results (accuracy / macro-F1):**

| Model | Standard split | Cold-start split |
|---|---|---|
| Majority baseline | 0.750 / 0.286 | 0.759 / 0.288 |
| Text-only | 0.746 / 0.645 | 0.682 / **0.532** |
| Chemistry-only | 0.771 / 0.670 | 0.569 / 0.437 |
| Hybrid | **0.776 / 0.676** | 0.592 / 0.456 |

**Finding:** chemistry and hybrid both beat text in-distribution (standard split), as expected. But on cold-start — held-out, never-seen drugs, the harder and more realistic test — **text-only wins outright**. A regularization sweep (C = 0.01, 0.1, 1, 10) confirms this isn't a tuning artifact: text beats hybrid at every setting, and the gap *widens* as regularization loosens, meaning the model over-relies on chemistry bits that don't transfer to unseen drugs.

**Interpretation:** DDI severity is driven by pharmacology — metabolism, transporters, target binding, QT effects — not just structural similarity. Morgan fingerprints are a weak proxy for interaction *mechanism*, so on genuinely unseen drugs they mislead the model more than they help.

**Conclusion:** Morgan-fingerprint structural features, as implemented, improve in-distribution performance but do not solve — and actively worsen — the cold-start generalization problem they were meant to fix. This is a validated negative result, not a bug. Future work should target pharmacology-aware features (drug targets, enzymes, pathways, ATC classes, side-effect profiles, or knowledge-graph embeddings) rather than raw molecular structure alone.
