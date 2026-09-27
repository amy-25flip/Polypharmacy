"""
Model 4 (research branch) - Step 2: train a TransE knowledge-graph embedding
on the compound/disease-relevant Hetionet subgraph produced by
prepare_kg_triples.py.

Output: a per-entity embedding table (processed/model4/kg_entity_embeddings.pt
+ kg_entity_to_idx.json) that downstream steps (co-attention fusion, and an
upgraded embedding-based explainability path) can look up a DrugBankID/
Gene/Disease/SideEffect node's vector for.

CPU-only, TransE (cheapest reasonable KG embedding model to train without a
GPU). Runs as a background job - this is expected to take a while on CPU.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT_ROOT / "processed" / "model4"
TRIPLES_PATH = OUT_DIR / "kg_triples.tsv"


def main() -> None:
    print("Loading triples factory...")
    tf = TriplesFactory.from_path(str(TRIPLES_PATH))
    training, testing = tf.split([0.95, 0.05], random_state=42)
    print(f"Entities: {tf.num_entities:,} | Relations: {tf.num_relations} | Triples: {tf.num_triples:,}")

    print("Training TransE (CPU)...")
    result = pipeline(
        training=training,
        testing=testing,
        model="TransE",
        model_kwargs=dict(embedding_dim=128),
        training_kwargs=dict(num_epochs=60, batch_size=1024),
        optimizer_kwargs=dict(lr=0.01),
        random_seed=42,
        device="cpu",
    )

    entity_embeddings = result.model.entity_representations[0](indices=None).detach()
    entity_to_id = tf.entity_to_id  # name -> row index into entity_embeddings

    torch.save(entity_embeddings, OUT_DIR / "kg_entity_embeddings.pt")
    with open(OUT_DIR / "kg_entity_to_idx.json", "w", encoding="utf-8") as f:
        json.dump(entity_to_id, f)

    metrics = result.metric_results.to_dict()
    with open(OUT_DIR / "kg_embedding_eval.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)

    print(f"Saved entity embeddings: {tuple(entity_embeddings.shape)}")
    print("Link-prediction eval (held-out 5% of triples):")
    print(json.dumps(metrics.get("both", metrics), indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
