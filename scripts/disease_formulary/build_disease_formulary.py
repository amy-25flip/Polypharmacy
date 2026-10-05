"""Rebuild the disease reference from Hetionet and reviewed, cited additions.

Run from any directory: python scripts/disease_formulary/build_disease_formulary.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import fda_indications  # noqa: E402  (reverse indication search helpers)

INPUT = Path(__file__).with_name("curated_formulary.json")
# Conditions added for wider specialty coverage (dermatology and everyday primary-care conditions).
NEW_CONDITIONS = Path(__file__).with_name("new_conditions.json")
SPECIALTIES = Path(__file__).with_name("specialties.json")
OUTPUT = ROOT / "processed" / "disease_formulary.json"
SUMMARY = ROOT / "processed" / "disease_formulary_summary.md"
# source key (casefolded name before merging) -> target key
MERGE_DISEASES = {"endogenous depression": "depression"}
# Written by apply_doctor_review.py from the returned clinician review workbook (optional).
DOCTOR_REVIEW = Path(__file__).with_name("doctor_review.json")
# Written by scripts/fda_labels/build_label_evidence.py (optional): each drug's FDA-label indications text.
LABEL_INDICATIONS = ROOT / "processed" / "label_indications.json"
LABEL_SOURCE = "fda-label:indicated"
GENERIC_WORDS = {"disease", "syndrome", "chronic", "primary", "acute", "disorder", "secondary", "type", "mellitus"}


def label_supports(terms: list[str], text: str) -> bool:
    """True if the label text names the condition: every key word of the name (or an alias) appears.

    Words of 7+ letters are matched by their first 7 letters so diabetes/diabetic and
    hypertension/hypertensive agree. Short aliases are ignored because they match too broadly.
    """
    text = text.lower()
    for term in terms:
        words = [w for w in re.findall(r"[a-z]+", term.lower()) if len(w) >= 4 and w not in GENERIC_WORDS]
        if len(term) >= 6 and words and all(w[:7] in text for w in words):
            return True
    return False


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
    conditions = list(curated["diseases"])
    if NEW_CONDITIONS.exists():
        added_conditions = json.loads(NEW_CONDITIONS.read_text(encoding="utf-8"))
        references = {**references, **added_conditions["sources"]}
        conditions += added_conditions["diseases"]
    synonyms = json.loads((ROOT / "processed" / "drug_aliases.json").read_text(encoding="utf-8"))["synonyms"]
    lookup = fda_indications.build_lookup(vocabulary, synonyms)
    curated_added = fda_added = 0
    route_lookups: dict[str, dict[str, str]] = {}
    for condition in conditions:
        name = condition["name"]
        key = condition.get("hetionet_name", name).casefold()
        disease = diseases.setdefault(key, {"name": name, "aliases": set(),
                                            "medicines": defaultdict(set)})
        disease["name"] = name
        disease["aliases"].update(condition.get("aliases", []))
        disease.setdefault("specialties", set()).update(condition.get("specialties", []))
        for field in ("note", "route_note"):
            if condition.get(field):
                disease[field] = condition[field]
        # Medicines whose FDA label lists the condition among its approved uses (single-ingredient labels only).
        route = condition.get("route_prefer")
        if route and route not in route_lookups:
            route_lookups[route] = fda_indications.build_lookup(vocabulary, synonyms, route)
        allowed = condition.get("fda_include")
        for drug in fda_indications.candidates(condition.get("fda_phrases", []), route_lookups.get(route, lookup)):
            if drug not in condition.get("fda_exclude", []) and (allowed is None or drug in allowed):
                disease["medicines"][drug].add(LABEL_SOURCE)
                fda_added += 1
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

    # An FDA label that names the condition among its approved uses corroborates a listing.
    label_marked = 0
    if LABEL_INDICATIONS.exists():
        indications = json.loads(LABEL_INDICATIONS.read_text(encoding="utf-8"))
        for disease in diseases.values():
            terms = [disease["name"], *disease["aliases"]]
            for medicine, citations in disease["medicines"].items():
                text = indications.get(medicine, {}).get("text")
                if text and label_supports(terms, text):
                    citations.add(LABEL_SOURCE)
                    label_marked += 1

    specialty_map = json.loads(SPECIALTIES.read_text(encoding="utf-8")) if SPECIALTIES.exists() else {}
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
        entry = {"id": did, "name": disease["name"],
                 "aliases": sorted(disease["aliases"], key=str.casefold),
                 "specialties": sorted(disease.get("specialties", set()) | set(specialty_map.get(disease["name"], [])),
                                       key=str.casefold),
                 "medicines": medicines}
        for field in ("note", "route_note"):
            if disease.get(field):
                entry[field] = disease[field]
        result.append(entry)
    result.sort(key=lambda d: d["name"].casefold())
    OUTPUT.write_text(json.dumps({"version": 1,
                                  "generated_by": "scripts/disease_formulary/build_disease_formulary.py",
                                  "diseases": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hetionet_count = sum(any(s.startswith("hetionet:") for m in d["medicines"] for s in m["sources"])
                         for d in result)
    curated_count = sum(any(not s.startswith(("hetionet:", "fda-label:")) for m in d["medicines"] for s in m["sources"])
                        for d in result)
    lines = ["# Disease formulary build summary", "",
             "Generated by `scripts/disease_formulary/build_disease_formulary.py`.", "",
             f"- App vocabulary: {len(vocabulary):,} names; DrugBank ID map: {len(name_to_id):,} names.",
             f"- Hetionet disease nodes with CtD/CpD edges: {len(seen_diseases)}.",
             f"- Hetionet diseases with at least three checkable medicines: {len(seen_diseases) - len(dropped)}.",
             f"- Final diseases: {len(result)}; with Hetionet provenance: {hetionet_count}; with curated provenance: {curated_count}.",
             f"- Curated source-to-medicine additions processed: {curated_added} (before deduplication).",
             f"- Clinician review applied: {review_removed} removals, {review_added} additions." if review
             else "- Clinician review: none applied yet.",
             f"- Listings whose FDA label names the condition among its approved uses: {label_marked}.",
             f"- Medicines suggested directly from FDA label indications for the added conditions: {fda_added}.", "",
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
                    for source in med["sources"] if not source.startswith(("hetionet:", "fda-label:"))}
    lines += [f"- {citation}: {references.get(citation, 'reviewer-added entry')}" for citation in sorted(used_sources)]
    lines += ["- fda-label:indicated: the medicine's FDA label (openFDA) names this condition among its approved uses."]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"PASS: {len(result)} diseases, {hetionet_count} with Hetionet edges, "
          f"{curated_count} with curated entries; {len(skipped)} skipped-for-review notes")
    print(f"Wrote {OUTPUT} and {SUMMARY}")


if __name__ == "__main__":
    main()
