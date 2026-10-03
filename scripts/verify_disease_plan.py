"""HTTP verification of the disease-plan backend (server supplied by caller)."""
from __future__ import annotations

import argparse
import itertools
import json
import time
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
    print("PASS parity: 20/20 pairs (10 documented, 10 undocumented) match /api/check severity and provenance")

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
    assert status == 200 and health == {"status": "ok", "known_drugs": 1902}
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
