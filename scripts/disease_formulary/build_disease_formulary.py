"""Rebuild the disease reference from Hetionet and reviewed, cited additions.

Run from any directory: python scripts/disease_formulary/build_disease_formulary.py
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = Path(__file__).with_name("curated_formulary.json")
OUTPUT = ROOT / "processed" / "disease_formulary.json"
SUMMARY = ROOT / "processed" / "disease_formulary_summary.md"
# source key (casefolded name before merging) -> target key
MERGE_DISEASES = {"endogenous depression": "depression"}
# Written by apply_doctor_review.py from the returned clinician review workbook (optional).
DOCTOR_REVIEW = Path(__file__).with_name("doctor_review.json")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def main() -> None:
    vocabulary = json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8"))
    vocab_by_norm = {name.casefold(): name for name in vocabulary}
    name_to_id = json.loads((ROOT / "processed" / "drug_name_to_drugbank_id.json").read_text(encoding="utf-8"))
    id_to_names = defaultdict(set)
    for name, drugbank_id in name_to_id.items():
        if name in vocab_by_norm:
            id_to_names[drugbank_id].add(vocab_by_norm[name])
    node_names = {}
    with (ROOT / "Datasets" / "hetionet-v1.0-nodes.tsv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["id"].startswith("Disease::"):
                node_names[row["id"]] = row["name"]

    edges = defaultdict(lambda: defaultdict(set))
    seen_diseases = set()
    edge_counts = defaultdict(int)
    with (ROOT / "Datasets" / "edges.sif").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            metaedge = row["metaedge"]
            if metaedge not in ("CtD", "CpD"):
                continue
            compound, disease = row["source"], row["target"]
            if not compound.startswith("Compound::") or disease not in node_names:
                continue
            seen_diseases.add(disease)
            drugbank_id = compound.split("::", 1)[1]
            for name in id_to_names.get(drugbank_id, ()):
                edges[node_names[disease]][name].add(f"hetionet:{metaedge}")
                edge_counts[metaedge] += 1

    curated = json.loads(INPUT.read_text(encoding="utf-8"))
    references = curated["sources"]
    diseases = {}
    dropped = []
    for disease_id in seen_diseases:
        raw_name = node_names[disease_id]
        medicines = edges.get(raw_name, {})
        if len(medicines) < 3:
            dropped.append((raw_name, len(medicines)))
            continue
        name = raw_name[0].upper() + raw_name[1:]
        diseases[raw_name.casefold()] = {"name": name, "aliases": set(), "medicines": medicines}

    skipped = list(curated.get("skipped_for_review", []))
    curated_added = 0
    for condition in curated["diseases"]:
        name = condition["name"]
        key = condition.get("hetionet_name", name).casefold()
        disease = diseases.setdefault(key, {"name": name, "aliases": set(),
                                            "medicines": defaultdict(set)})
        disease["name"] = name
        disease["aliases"].update(condition.get("aliases", []))
        if condition.get("hetionet_name"):
            disease["aliases"].add(condition["hetionet_name"])
        for citation, candidates in condition["medicines"].items():
            if citation not in references:
                raise ValueError(f"Missing source URL for {citation}")
            for candidate in candidates:
                canonical = vocab_by_norm.get(candidate.casefold())
                if canonical is None:
                    skipped.append(f"{name}: {candidate} absent from application vocabulary")
                    continue
                disease["medicines"][canonical].add(citation)
                curated_added += 1

    # Hetionet's Disease Ontology splits some conditions a doctor treats as one entry.
    for source_key, target_key in MERGE_DISEASES.items():
        source, target = diseases.pop(source_key, None), diseases.get(target_key)
        if source is None or target is None:
            continue
        target["aliases"].add(source["name"])
        target["aliases"].update(source["aliases"])
        for medicine, citations in source["medicines"].items():
            target["medicines"][medicine] = set(target["medicines"].get(medicine, set())) | set(citations)

    # Clinician review: explicit removals and additions override both sources.
    review = json.loads(DOCTOR_REVIEW.read_text(encoding="utf-8")) if DOCTOR_REVIEW.exists() else None
    review_removed = review_added = 0
    if review:
        by_name = {d["name"].casefold(): d for d in diseases.values()}
        credit = f"Clinician review ({review.get('reviewer') or 'unnamed'})"
        for item in review["removed"]:
            disease = by_name.get(item["disease"].casefold())
            medicine = vocab_by_norm.get(item["medicine"].casefold())
            if disease and medicine in disease["medicines"]:
                del disease["medicines"][medicine]
                review_removed += 1
            else:
                skipped.append(f"Review removal not applied (not on the list): {item['disease']}: {item['medicine']}")
        for item in review["added"]:
            disease = by_name.get(item["disease"].casefold())
            medicine = vocab_by_norm.get(item["medicine"].casefold())
            if disease and medicine:
                disease["medicines"][medicine].add(credit)
                review_added += 1
            else:
                skipped.append(f"Review addition not applied: {item['disease']}: {item['medicine']}")
        skipped.extend(review.get("requests_not_applied", []))

    result = []
    ids_seen = set()
    for disease in diseases.values():
        if not disease["medicines"]:
            skipped.append(f"{disease['name']}: no checkable medicine remains")
            continue
        did = slug(disease["name"])
        if did in ids_seen:
            raise ValueError(f"Duplicate disease ID: {did}")
        ids_seen.add(did)
        medicines = [
            {"name": name, "sources": sorted(sources)}
            for name, sources in sorted(disease["medicines"].items(), key=lambda item: item[0].casefold())
        ]
        result.append({"id": did, "name": disease["name"],
                       "aliases": sorted(disease["aliases"], key=str.casefold),
                       "medicines": medicines})
    result.sort(key=lambda d: d["name"].casefold())
    OUTPUT.write_text(json.dumps({"version": 1,
                                  "generated_by": "scripts/disease_formulary/build_disease_formulary.py",
                                  "diseases": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hetionet_count = sum(any(s.startswith("hetionet:") for m in d["medicines"] for s in m["sources"])
                         for d in result)
    curated_count = sum(any(not s.startswith("hetionet:") for m in d["medicines"] for s in m["sources"])
                        for d in result)
    lines = ["# Disease formulary build summary", "",
             "Generated by `scripts/disease_formulary/build_disease_formulary.py`.", "",
             f"- App vocabulary: {len(vocabulary):,} names; DrugBank ID map: {len(name_to_id):,} names.",
             f"- Hetionet disease nodes with CtD/CpD edges: {len(seen_diseases)}.",
             f"- Hetionet diseases with at least three checkable medicines: {len(seen_diseases) - len(dropped)}.",
             f"- Final diseases: {len(result)}; with Hetionet provenance: {hetionet_count}; with curated provenance: {curated_count}.",
             f"- Curated source-to-medicine additions processed: {curated_added} (before deduplication).",
             f"- Clinician review applied: {review_removed} removals, {review_added} additions." if review
             else "- Clinician review: none applied yet.", "",
             "## Diseases and medicine counts", "",
             "| Disease | Medicines |", "|---|---:|",]
    lines += [f"| {d['name']} | {len(d['medicines'])} |" for d in result]
    lines += ["", "## Dropped Hetionet diseases (<3 checkable medicines)", ""]
    lines += [f"- {name}: {count}" for name, count in sorted(dropped)] or ["- None."]
    lines += ["", "## Skipped for review", ""]
    lines += [f"- {item}" for item in skipped] or ["- None."]
    lines += ["", "## Source notes", "",
              "Hetionet `CtD` means compound-treats-disease; `CpD` means compound-palliates-disease. "
              "These are knowledge-graph associations, not a recommendation or evidence of effectiveness "
              "for a particular patient. Curated citations identify the relevant guidance or essential "
              "medicines section; inclusion is a browsing aid, never prescribing advice.", ""]
    used_sources = {source for disease in result for med in disease["medicines"]
                    for source in med["sources"] if not source.startswith("hetionet:")}
    lines += [f"- {citation}: {references.get(citation, 'reviewer-added entry')}" for citation in sorted(used_sources)]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: {len(result)} diseases, {hetionet_count} with Hetionet edges, "
          f"{curated_count} with curated entries; {len(skipped)} skipped-for-review notes")
    print(f"Wrote {OUTPUT} and {SUMMARY}")


if __name__ == "__main__":
    main()
