"""HTTP verification of the disease-plan backend (server supplied by caller)."""
from __future__ import annotations

import argparse
import itertools
import json
import time
import urllib.parse
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def request(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    raw = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(base + path, data=raw, headers={"Content-Type": "application/json"} if raw else {},
                  method="POST" if raw else "GET")
    try:
        with urlopen(req, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8790")
    base = parser.parse_args().base_url.rstrip("/")
    vocab = json.loads((ROOT / "processed" / "drug_vocabulary.json").read_text(encoding="utf-8"))
    vocab_set = set(vocab)
    lowered = {name.lower(): name for name in vocab}
    documented = set(json.loads((ROOT / "processed" / "documented_pairs.json").read_text(encoding="utf-8")))

    status, data = request(base, "/api/diseases")
    assert status == 200 and data["diseases"]
    status, diabetes = request(base, "/api/diseases?q=diabetes")
    assert status == 200 and any("diabetes" in d["name"].lower() for d in diabetes["diseases"])
    status, kidney = request(base, "/api/diseases?q=kidney")
    assert status == 200 and any("kidney" in d["name"].lower() for d in kidney["diseases"])
    print(f"PASS diseases: {len(data['diseases'])} total; diabetes and kidney searches resolve")
    # Fuzzy matching is a typo fallback only: a direct hit must not be padded with unrelated diseases.
    assert all("diabet" in (d["name"] + " ".join(d["aliases"])).lower() for d in diabetes["diseases"]), diabetes
    status, typo = request(base, "/api/diseases?q=diabtes")
    assert status == 200 and any("diabetes" in d["name"].lower() for d in typo["diseases"]), typo
    ids = {d["id"] for d in data["diseases"]}
    assert "depression" in ids and "endogenous-depression" not in ids, "depression entries must be merged"
    print("PASS search: direct hits are not padded by fuzzy matches; typo 'diabtes' still finds diabetes; depression merged")

    checked = 0
    for disease in data["diseases"]:
        status, item = request(base, f"/api/diseases/{disease['id']}/medicines")
        assert status == 200
        assert all(m["name"] in vocab_set and m["sources"] for m in item["medicines"])
        checked += 1
    status, _ = request(base, "/api/diseases/nonexistent-condition/medicines")
    assert status == 404
    print(f"PASS formulary: all {checked} disease medicine lists use vocabulary names with sources; unknown ID is 404")

    common = [n for n in ["Warfarin", "Amiodarone", "Metformin", "Amlodipine", "Losartan",
                          "Atorvastatin", "Clopidogrel", "Omeprazole", "Ibuprofen", "Dapagliflozin",
                          "Levothyroxine", "Rifampicin", "Sertraline", "Albuterol", "Digoxin",
                          "Acetylsalicylic acid", "Spironolactone", "Apixaban", "Nitrofurantoin"] if n in vocab_set]
    yes, no = [], []
    for a, b in itertools.combinations(common, 2):
        key = "|".join(sorted([a.lower(), b.lower()]))
        (yes if key in documented else no).append((a, b))
    pairs = yes[:10] + no[:10]
    assert len(pairs) >= 20 and len(yes) >= 10 and len(no) >= 10
    for a, b in pairs:
        status, screen = request(base, "/api/screen-candidates", {"selected": [a], "candidates": [b]})
        assert status == 200
        status, check = request(base, "/api/check", {"drugs": [a, b]})
        assert status == 200
        flag = screen["results"][0]["flags"][0]
        reference = check["regimen"]["pairs"][0]
        assert flag["severity"] == reference["severity"], (a, b, flag, reference)
        assert flag["is_documented"] == reference["is_documented"]
        assert flag["severity_basis"] == reference["severity_basis"], (a, b, flag, reference)
    print("PASS parity: 20/20 pairs (10 documented, 10 undocumented) match /api/check severity and provenance")

    # A documented pair must show its documented severity, never the model's guess. The model alone
    # shows documented Major pairs as Minor, so check the pairs where it is most wrong.
    severity_by_pair = json.loads((ROOT / "processed" / "documented_severity.json").read_text(encoding="utf-8"))
    majors = [key.split("|") for key in severity_by_pair["Major"]
              if all(name in lowered for name in key.split("|"))][:60]
    assert len(majors) >= 40
    for a, b in majors:
        status, check = request(base, "/api/check", {"drugs": [lowered[a], lowered[b]]})
        pair = check["regimen"]["pairs"][0]
        assert status == 200 and pair["severity"] == "Major" and pair["severity_basis"] == "documented", (a, b, pair)
        status, screen = request(base, "/api/screen-candidates",
                                 {"selected": [lowered[a]], "candidates": [lowered[b]]})
        assert screen["results"][0]["flags"][0]["severity"] == "Major", (a, b)
    status, check = request(base, "/api/check", {"drugs": ["Warfarin", "Acetylsalicylic acid"]})
    assert check["regimen"]["pairs"][0]["severity"] == "Major"
    print(f"PASS documented severity: {len(majors)} documented Major pairs are Major in both endpoints; warfarin + aspirin is Major")

    # Fourth state: an undocumented pair with no signal is "None" (no reaction on record).
    none_pairs = []
    for a, b in itertools.combinations(common, 2):
        status, check = request(base, "/api/check", {"drugs": [a, b]})
        pair = check["regimen"]["pairs"][0]
        if pair["severity"] == "None":
            assert pair["severity_basis"] == "no_record" and not pair["is_documented"]
            assert "not proof" in pair["severity_notice"]
            none_pairs.append((a, b))
    assert none_pairs, "expected at least one no-reaction pair among common drugs"
    a, b = none_pairs[0]
    status, screen = request(base, "/api/screen-candidates", {"selected": [a], "candidates": [b]})
    assert screen["results"][0]["worst_severity"] == "None" and screen["selected_summary"]["counts"]["None"] == 0
    status, plan = request(base, "/api/screen-candidates", {"selected": [a, b], "candidates": []})
    assert plan["selected_summary"]["overall_severity"] == "None" and plan["selected_summary"]["counts"]["None"] == 1
    print(f"PASS no-reaction state: {len(none_pairs)} common pairs, e.g. {a} + {b}, consistent in both endpoints")

    # Drugs with no records of their own are checked through a relative, and say so.
    for name, proxy in [("Gliclazide", "Glimepiride"), ("Carbimazole", "Methimazole")]:
        assert name in vocab_set
        status, check = request(base, "/api/check", {"drugs": [name, "Warfarin"]})
        pair = check["regimen"]["pairs"][0]
        assert pair["estimated_from"][0]["proxy"] == proxy and pair["is_documented"] is False
        assert pair["severity_basis"] in ("estimated", "no_record", "inferred")
        status, ref = request(base, "/api/check", {"drugs": [proxy, "Warfarin"]})
        assert pair["severity"] == ref["regimen"]["pairs"][0]["severity"], (name, pair, ref)
    status, dup = request(base, "/api/check", {"drugs": ["Gliclazide", "Glimepiride"]})
    assert dup["regimen"]["pairs"][0]["severity_basis"] == "duplicate_class"
    status, hits = request(base, "/api/drugs/search?q=aspirin")
    assert hits[0]["name"] == "Acetylsalicylic acid" and hits[0]["matched_via_synonym"] == "aspirin"
    status, hits = request(base, "/api/drugs/search?q=paracetamol")
    assert hits[0]["name"] == "Acetaminophen"
    print("PASS aliases: gliclazide/carbimazole checked as estimates; duplicate class flagged; aspirin and paracetamol are found")

    # Patient factors: cautions depend on age and kidney function, and only on what was entered.
    status, none = request(base, "/api/patient-cautions", {"drugs": ["Metformin", "Diazepam"]})
    assert status == 200 and none["cautions"] == []
    status, renal = request(base, "/api/patient-cautions", {"drugs": ["Metformin", "Ibuprofen"], "egfr": 15})
    levels = {c["drug"]: c["level"] for c in renal["cautions"]}
    assert levels == {"Metformin": "Avoid", "Ibuprofen": "Avoid"}, renal
    status, mild = request(base, "/api/patient-cautions", {"drugs": ["Metformin"], "egfr": 30})
    assert [c["level"] for c in mild["cautions"]] == ["Use with caution"], mild
    status, aged = request(base, "/api/patient-cautions", {"drugs": ["Diazepam", "Warfarin"], "age": 72})
    assert [(c["drug"], c["level"]) for c in aged["cautions"]] == [("Diazepam", "Avoid")], aged
    assert all(c["source"] and c["url"].startswith("http") for c in renal["cautions"] + aged["cautions"])
    status, _ = request(base, "/api/patient-cautions", {"drugs": ["Metformin"], "age": 500})
    assert status == 422
    print("PASS patient factors: renal and age cautions trigger only when entered, carry a source, and bad input is 422")

    # Pair-specific evidence from FDA label text, when the label index has been built.
    if (ROOT / "processed" / "label_interactions.json").exists():
        status, check = request(base, "/api/check", {"drugs": ["Amiodarone", "Warfarin"]})
        pair = check["regimen"]["pairs"][0]
        assert pair["label_evidence"] and "Bleeding" in pair["label_effects"], pair
        status, screen = request(base, "/api/screen-candidates", {"selected": ["Warfarin"], "candidates": ["Amiodarone"]})
        flag = screen["results"][0]["flags"][0]
        assert flag["adverse_effect_source"] == "label" and "Bleeding" in flag["adverse_effects"], flag
        assert flag["label_evidence"]
        print("PASS label evidence: amiodarone + warfarin carries the FDA label sentence and its named effect in both endpoints")

    # Specialties and the wider condition list (dermatology and everyday primary-care conditions).
    status, specs = request(base, "/api/specialties")
    names = {item["name"]: item["disease_count"] for item in specs["specialties"]}
    assert status == 200 and names.get("Dermatology", 0) >= 30 and len(names) >= 12, names
    status, derm = request(base, "/api/diseases?q=&specialty=Dermatology")
    assert derm["diseases"] and all("Dermatology" in d["specialties"] for d in derm["diseases"])
    for query, expected in [("acne", "Acne vulgaris"), ("ringworm", "Dermatophytosis of skin"), ("khujli", "Scabies"),
                            ("piles", "Haemorrhoids"), ("loose motions", "Acute gastroenteritis"), ("PCOD", "Polycystic ovary syndrome"),
                            ("UTI", "Urinary tract infection"), ("fever", "Undifferentiated fever")]:
        status, found = request(base, "/api/diseases?q=" + urllib.parse.quote(query))
        assert any(d["name"] == expected for d in found["diseases"]), (query, [d["name"] for d in found["diseases"]])
    status, narrowed = request(base, "/api/diseases?q=tinea&specialty=Cardiology")
    assert narrowed["diseases"] == []
    status, fever = request(base, "/api/diseases?q=fever")
    assert any("Antibiotics are not routine" in (d.get("note") or "") for d in fever["diseases"])
    status, seb = request(base, "/api/diseases?q=seborrhoeic")
    assert any("oral ketoconazole" in (d.get("route_note") or "") for d in seb["diseases"])
    print(f"PASS conditions: {len(names)} specialties; Dermatology has {names['Dermatology']} diagnoses; aliases like ringworm, khujli, piles, PCOD and loose motions resolve; cautions are carried")

    # Drugs the interaction database cannot check are accepted but reported as not checked, never as safe.
    status, nc = request(base, "/api/check", {"drugs": ["Mupirocin", "Warfarin"]})
    pair = nc["regimen"]["pairs"][0]
    assert pair["severity"] == "None" and pair["severity_basis"] == "no_data" and "not checked" in pair["severity_notice"].lower(), pair
    status, nc2 = request(base, "/api/screen-candidates", {"selected": ["Warfarin"], "candidates": ["Mupirocin", "Domperidone"]})
    for result in nc2["results"]:
        assert result["flags"][0]["severity_basis"] == "no_data" and result["flags"][0]["severity_notice"], result
    status, hits = request(base, "/api/drugs/search?q=mupiro")
    assert hits and hits[0]["name"] == "Mupirocin"
    print("PASS not-checked drugs: Mupirocin and Domperidone can be added; their pairs say Not checked in both endpoints")

    # Key dermatology interactions come out as documented Major pairs.
    for a, b in [("Isotretinoin", "Doxycycline"), ("Acitretin", "Methotrexate"), ("Methotrexate", "Trimethoprim")]:
        status, check = request(base, "/api/check", {"drugs": [a, b]})
        assert check["regimen"]["pairs"][0]["severity"] == "Major", (a, b)
    status, preg = request(base, "/api/patient-cautions", {"drugs": ["Isotretinoin", "Doxycycline", "Lisinopril", "Metformin"], "pregnancy": "pregnant"})
    assert {c["drug"] for c in preg["cautions"]} == {"Isotretinoin", "Doxycycline", "Lisinopril"}, preg
    assert all(c["level"] == "Avoid" and c["factor"] == "pregnancy" for c in preg["cautions"])
    status, none = request(base, "/api/patient-cautions", {"drugs": ["Isotretinoin"]})
    assert none["cautions"] == []
    # "Could become pregnant" triggers the teratogens that need contraception, not every pregnancy caution.
    status, possible = request(base, "/api/patient-cautions", {"drugs": ["Isotretinoin", "Lisinopril", "Methotrexate"], "pregnancy": "possible"})
    assert {c["drug"] for c in possible["cautions"]} == {"Isotretinoin", "Methotrexate"}, possible
    assert all(c["trigger"] == "pregnancy possible" for c in possible["cautions"])
    status, bad = request(base, "/api/patient-cautions", {"drugs": ["Isotretinoin"], "pregnancy": "maybe"})
    assert status == 422
    print("PASS dermatology safety: isotretinoin + doxycycline, acitretin + methotrexate and methotrexate + trimethoprim are Major; pregnancy cautions fire only when ticked")

    # Review fixes: class warnings outrank a weak model guess, brands bundle every ingredient, lists are grouped.
    for a, b, floor in [("Lisinopril", "Spironolactone", "Moderate"), ("Enalapril", "Amiloride", "Moderate"),
                        ("Ramipril", "Naproxen", "Moderate"), ("Losartan", "Spironolactone", "Moderate")]:
        status, check = request(base, "/api/check", {"drugs": [a, b]})
        pair = check["regimen"]["pairs"][0]
        assert pair["severity"] in ("Moderate", "Major"), (a, b, pair)
        if pair["severity_basis"] == "class_rule":
            assert pair["severity"] == floor and "class-level warning" in pair["severity_notice"], pair
        status, screen = request(base, "/api/screen-candidates", {"selected": [a], "candidates": [b]})
        assert screen["results"][0]["flags"][0]["severity"] == pair["severity"], (a, b)
    status, check = request(base, "/api/check", {"drugs": ["Lisinopril", "Spironolactone"]})
    assert check["regimen"]["pairs"][0]["severity_basis"] in ("class_rule", "documented", "inferred")
    status, bundle = request(base, "/api/drugs/search?q=zerodol%20p")
    assert bundle[0]["bundle"] == ["Aceclofenac", "Acetaminophen"] and bundle[0]["matched_via_brand"] == "zerodol p", bundle[:2]
    status, single = request(base, "/api/drugs/search?q=dolo%20650")
    assert single[0]["name"] == "Acetaminophen" and "bundle" not in single[0]
    status, ht = request(base, "/api/diseases/hypertension/medicines")
    groups = {m["name"]: m["group"] for m in ht["medicines"]}
    assert groups["Amlodipine"] == "Usual first choices" and groups["Atorvastatin"].startswith("Lowers heart risk")
    assert any(m["group_collapsed"] for m in ht["medicines"]) and sum(1 for g in groups.values() if g == "Usual first choices") >= 10
    status, t2 = request(base, "/api/diseases/type-2-diabetes-mellitus/medicines")
    by = {m["name"]: m for m in t2["medicines"]}
    assert by["Losartan"]["group"].startswith("Not for glucose control") and by["Metformin"]["group"].startswith("Common glucose-lowering")
    status, tb = request(base, "/api/diseases?q=tuberculosis")
    assert "regimen" in (tb["diseases"][0]["note"] or "")
    status, gi = request(base, "/api/diseases/acute-gastroenteritis/medicines")
    assert gi["medicines"][0]["name"] == "Oral rehydration salts" or any(m["name"] == "Oral rehydration salts" for m in gi["medicines"])
    print("PASS review fixes: class warnings raise ACE/ARB pairs, combination brands bundle ingredients, long lists are grouped with TB as a regimen and ORS listed")

    status, result = request(base, "/api/screen-candidates",
                             {"selected": ["Warfarin", "warfarin"],
                              "candidates": ["Warfarin", "NOT_A_DRUG", "Amiodarone"]})
    assert status == 200 and len(result["results"]) == 2
    assert result["results"][0]["worst_severity"] is None and not result["results"][0]["flags"]
    assert result["unmatched"] == ["NOT_A_DRUG"]
    assert result["adverse_effect_basis"].startswith("Side effects both medicines")
    print("PASS self-comparison, case-insensitive deduplication, unmatched reporting, and adverse-effect basis")

    for field in ("selected", "candidates"):
        body = {"selected": [], "candidates": []}
        body[field] = ["Warfarin"] * 101
        status, _ = request(base, "/api/screen-candidates", body)
        assert status == 422
    print("PASS >100-name validation: selected and candidates both return 422")

    status, health = request(base, "/api/health")
    assert status == 200 and health == {"status": "ok", "known_drugs": len(vocab)}
    status, old = request(base, "/api/check", {"drugs": ["Warfarin", "Amiodarone"]})
    assert status == 200 and old["regimen"]["overall_severity"] == "Major"
    print("PASS old endpoints: health unchanged; Warfarin + Amiodarone is Major")

    selected = [n for n in common if n in vocab_set][:10]
    candidates = [n for n in vocab if n not in selected][:70]
    body = {"selected": selected, "candidates": candidates}
    request(base, "/api/screen-candidates", body)  # warm model, chemistry, and pair cache
    t0 = time.perf_counter()
    status, timed = request(base, "/api/screen-candidates", body)
    elapsed = time.perf_counter() - t0
    assert status == 200 and len(timed["results"]) == 70 and len(timed["selected_summary"]["pairs"]) == 45
    assert elapsed < 1.5, f"warm 70x10 timing {elapsed:.3f}s exceeded 1.5s"
    print(f"PASS warm timing: 70 candidates x 10 selected = {elapsed:.3f}s (<1.5s)")
    print("ALL VERIFICATIONS PASSED")


if __name__ == "__main__":
    main()
