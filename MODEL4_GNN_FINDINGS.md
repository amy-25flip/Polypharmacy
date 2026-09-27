# Model 4 — GNN architecture experiment (from the team's diagram) — findings

**Hypothesis:** the team's proposed architecture — GATv2 molecular graph encoder + Hetionet knowledge-graph (TransE) embeddings + a drug-interaction graph refined by GraphSAGE message passing + symmetric co-attention + a bilinear decoder + a prediction head — would outperform Model 1 (TF-IDF char n-gram + logistic regression) by using real chemical structure and knowledge-graph relationships instead of just drug-name text patterns.

**What was built** (`scripts/model4/`): every non-patient component of the diagram, in full —
- `prepare_kg_triples.py` + `train_kg_embeddings.py`: TransE embeddings (128-dim) trained on a 234,512-triple compound/disease-relevant subgraph of Hetionet (21,646 entities; link-prediction eval confirms the embeddings capture real graph structure, well above random).
- `molecular_graph.py`: SMILES → PyTorch Geometric molecular graph → 2-layer GATv2 encoder → 128-dim drug embedding, with attention weights exposed for explainability.
- `model4_architecture.py`: the drug-interaction graph (GraphSAGE, 2 layers) + symmetric co-attention + multi-modal fusion + bilinear decoder + MLP prediction head — trained end-to-end.
- `explain_model4.py`: working molecular-attention (panel 10.1) and interaction-graph-neighbor (panel 10.2) explainability, using the trained checkpoint.

Patient clinical features (diagram panel 3C) were explicitly excluded — no dataset exists with real patient-drug-pair interaction outcomes to train that branch on (see project notes); it isn't part of this comparison.

**Method:** restricted to the 48,784 pairs (982 of 1,902 drugs) where both drugs have a resolved SMILES *and* a Hetionet node — a real constraint of the graph/chemistry approach that Model 1 doesn't have (Model 1 only needs drug-name text, so it covers all 1,902 drugs). Model 1 was retrained from scratch on this *identical* subset and identical standard/cold-start splits (same protocol as the chemistry-model experiment) for a fair, apples-to-apples comparison. The drug-interaction graph used for message passing was built only from training-split pairs in both protocols, so test-pair labels never leak into the graph structure being evaluated. Trained to 400 epochs (loss plateaued; 200→400 epochs gave diminishing but still-positive returns, ruling out "just needed more training").

**Results (accuracy / macro-F1, on the identical 48,784-pair subset):**

| Model | Standard split | Cold-start split |
|---|---|---|
| Majority baseline | 0.751 / 0.286 | 0.758 / 0.287 |
| Model 1 (TF-IDF + LogReg), same subset | **0.739 / 0.616** | **0.656 / 0.530** |
| Model 4 (GNN), 400 epochs | 0.676 / 0.593 | 0.487 / 0.403 |

**Finding:** Model 1 beats Model 4 on both accuracy and macro-F1, on both protocols — despite Model 4 using real molecular structure and knowledge-graph relationships that Model 1 doesn't have access to at all. The gap is largest on cold-start (0.530 vs 0.403 macro-F1), which is the harder, more realistic generalization test.

**Interpretation:** this is the same pattern already found with the chemistry-only model ([CHEMISTRY_MODEL_FINDINGS.md](CHEMISTRY_MODEL_FINDINGS.md)) — DDInter's severity labels correlate more strongly with drug-name lexical patterns (pharmacologic-class naming conventions like "-statin", "-mab", "-cillin" that a character n-gram model picks up directly) than with the graph/structural signal a GNN of this scale can extract on CPU-only training with a few hundred thousand triples and ~1,000 nodes. A GNN's real advantage — generalizing via structural/relational similarity to drugs it wasn't trained on — should show up most on the cold-start split, and it's exactly there that it falls furthest behind, not closer.

**Conclusion:** the full diagrammed GNN architecture works end-to-end (trains, evaluates, explains) but is a **validated negative result for this dataset and scale**, not a bug — consistent with every other structure-based approach tried in this project (Model 2, and the AE component dropped from HODDI for label leakage). It is kept as a documented research branch (`scripts/model4/`, `processed/model4/`) and is **not** integrated into the deployed production API, which still runs Model 1. Future work that might close the gap: larger-scale pretraining of the molecular/KG encoders on data outside this project (e.g. a pretrained ChemBERTa/MolCLR checkpoint instead of a GATv2 trained from scratch on ~1,000 molecules), or a KG embedding trained on the full 2.25M-edge Hetionet graph with a GPU rather than the 234K-edge compound-relevant subgraph used here.
