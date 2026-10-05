"""Check that every medicine cited to an ICMR Standard Treatment Workflow appears in that workflow's text.

Run from any directory: python scripts/disease_formulary/verify_icmr_citations.py
Needs PyMuPDF (pip install pymupdf). Downloads each cited workflow PDF once into Datasets/icmr_stw/
(not tracked) and exits with an error if a cited medicine is not named in its workflow. A mention is
evidence the workflow discusses the medicine, not that it is first-line; a clinician still reviews each list.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("new_conditions.json")
CACHE = ROOT / "Datasets" / "icmr_stw"

# Other names the workflows use for the same drug.
SYNONYMS = {
    "acetaminophen": ["paracetamol", "acetaminophen"], "valaciclovir": ["valacyclovir", "valaciclovir"],
    "acyclovir": ["acyclovir", "aciclovir"], "cyclosporine": ["cyclosporin"], "mycophenolate mofetil": ["mycophenolate"],
    "fusidic acid": ["fusidic"], "cephalexin": ["cephalexin", "cefalexin"], "azelaic acid": ["azelaic"],
    "acetylsalicylic acid": ["aspirin", "acetylsalicylic"], "sulfamethoxazole": ["sulfamethoxazole", "co-trimoxazole", "cotrimoxazole"],
    "polyethylene glycol": ["polyethylene glycol", "peg"], "calcipotriol": ["calcipotriol", "calcipotriene"],
    "insulin human": ["insulin", "nph", "regular"], "insulin glargine": ["glargine"], "insulin detemir": ["detemir"], "zinc sulfate": ["zinc"], "oral rehydration salts": ["rehydration"], "selenium sulfide": ["selenium sulphide", "selenium sulfide"],
}


def words_for(medicine: str) -> list[str]:
    base = re.sub(r"\s*\(.*?\)", "", medicine).strip().lower()
    return SYNONYMS.get(base) or [base]


def main() -> None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("Install PyMuPDF first: pip install pymupdf")
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    urls = {title: url for title, url in data["sources"].items() if "icmr.gov.in/icmrobject" in url}
    CACHE.mkdir(parents=True, exist_ok=True)
    texts: dict[str, str] = {}
    for title, url in urls.items():
        path = CACHE / url.rsplit("/", 1)[-1]
        if not path.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            path.write_bytes(urllib.request.urlopen(request, timeout=60).read())
        texts[title] = " ".join(page.get_text() for page in fitz.open(path)).lower()

    checked = 0
    missing: list[tuple[str, str, str]] = []
    for condition in data["diseases"]:
        for title, medicines in condition["medicines"].items():
            if title not in texts:
                continue
            for medicine in medicines:
                checked += 1
                if not any(word in texts[title] for word in words_for(medicine)):
                    missing.append((condition["name"], title, medicine))
    for condition, title, medicine in missing:
        print(f"NOT FOUND: {medicine} for {condition} in '{title}'")
    print(f"{checked} ICMR-cited medicines checked against {len(texts)} workflows; {len(missing)} not found")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
