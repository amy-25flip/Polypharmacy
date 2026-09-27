"""Curated Indian trade-name lookup backed by the processed vocabulary."""
from __future__ import annotations

import json
import os
from pathlib import Path


def normalize_brand_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


_DEFAULT_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "processed"
_BRAND_DATA_PATH = Path(
    os.environ.get("POLYGUARD_PROCESSED_DIR", str(_DEFAULT_PROCESSED_DIR))
) / "indian_brand_names.json"
with open(_BRAND_DATA_PATH, encoding="utf-8") as _brand_file:
    BRAND_NAMES: dict[str, list[str]] = json.load(_brand_file)


def lookup_brand_matches(query: str) -> list[tuple[str, list[str]]]:
    """Return matching ``(brand, generics)`` pairs, with an exact hit first."""
    normalized = normalize_brand_name(query)
    if not normalized:
        return []
    if normalized in BRAND_NAMES:
        return [(normalized, BRAND_NAMES[normalized])]
    return [
        (brand, generics)
        for brand, generics in BRAND_NAMES.items()
        if normalized in brand
    ]


def lookup_brand_name(query: str) -> list[str]:
    """Return deduplicated vocabulary names for an exact/substring brand query."""
    results: list[str] = []
    for _, generics in lookup_brand_matches(query):
        for generic in generics:
            if generic not in results:
                results.append(generic)
    return results
