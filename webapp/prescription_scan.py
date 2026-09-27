"""Gemini-assisted prescription image extraction with vocabulary suggestions.

This module deliberately stops at extraction and suggestion. Its output is
untrusted clinical input: the frontend must require a clinician to confirm or
reject every medicine before it can enter an interaction check.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from brand_names import lookup_brand_name


NOT_CONFIGURED_ERROR = (
    "Prescription scanning is not configured on this server (GEMINI_API_KEY not set)."
)

EXTRACTION_PROMPT = """
Read this prescription image and extract only medicines that are visibly written.
Do not infer medicines that are not present. Return strict JSON only, with no
markdown fences or commentary, in exactly this shape:
{
  "source_guess": "string or null",
  "date_guess": "string or null",
  "medicines": [
    {
      "raw_text": "the exact visible text",
      "drug_name_guess": "best medicine-name reading",
      "generic_name_guess": "best active-ingredient name if the visible name looks like a brand, otherwise null",
      "dosage": "string or null",
      "frequency_or_timing_guess": "string or null",
      "confidence_notes": "brief uncertainty note or null"
    }
  ],
  "warnings": ["any image-quality, handwriting, ambiguity, or completeness warnings"]
}
If no medicine can be read, return an empty medicines list and explain why in warnings.
Every field must be present. This output will be reviewed by a doctor and must not
be described as verified. Set generic_name_guess to null when drug_name_guess
already appears to be a generic name or when there is no reasonable ingredient guess.
""".strip()


def _strip_code_fences(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _vocab_matches(
    query: str,
    drug_vocab: list[str],
    fuzz_module: Any,
    process_module: Any,
) -> list[str]:
    """Mirror /api/drugs/search ordering, limited to five suggestions."""
    query = query.strip()
    if not query:
        return []
    query_lower = query.lower()
    prefix_hits = [name for name in drug_vocab if name.lower().startswith(query_lower)]
    substring_hits = [
        name for name in drug_vocab
        if query_lower in name.lower() and name not in prefix_hits
    ]
    results = sorted(prefix_hits) + sorted(substring_hits)
    if len(results) < 5:
        fuzzy_matches = process_module.extract(
            query, drug_vocab, scorer=fuzz_module.WRatio, limit=5
        )
        for name, score, _ in fuzzy_matches:
            if score >= 60 and name not in results:
                results.append(name)
    return results[:5]


def scan_prescription(
    image_bytes: bytes,
    content_type: str,
    drug_vocab: list[str],
    fuzz_module: Any,
    process_module: Any,
) -> dict:
    """Extract candidates from an image; return structured errors, never raw failures."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"error": NOT_CONFIGURED_ERROR}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                EXTRACTION_PROMPT,
                types.Part.from_bytes(data=image_bytes, mime_type=content_type),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        response_text = response.text or ""
    except Exception as exc:
        return {
            "source_guess": None,
            "date_guess": None,
            "medicines": [],
            "warnings": [f"The prescription image could not be scanned: {exc}"],
        }

    try:
        parsed = json.loads(_strip_code_fences(response_text))
        if not isinstance(parsed, dict):
            raise ValueError("model response was not a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "source_guess": None,
            "date_guess": None,
            "medicines": [],
            "warnings": [
                f"The scanner returned an unreadable response ({exc}). Add medicines manually."
            ],
        }

    medicines = parsed.get("medicines")
    if not isinstance(medicines, list):
        medicines = []

    normalized_medicines = []
    for item in medicines:
        if not isinstance(item, dict):
            continue
        guess = str(item.get("drug_name_guess") or "").strip()
        generic_guess_value = item.get("generic_name_guess")
        generic_guess = (
            str(generic_guess_value).strip() if generic_guess_value is not None else None
        )
        suggestions: list[str] = []
        for candidate_query in (guess, generic_guess or ""):
            for candidate in lookup_brand_name(candidate_query):
                if candidate not in suggestions:
                    suggestions.append(candidate)
        for candidate in _vocab_matches(guess, drug_vocab, fuzz_module, process_module):
            if candidate not in suggestions:
                suggestions.append(candidate)
        normalized_medicines.append(
            {
                "raw_text": str(item.get("raw_text") or ""),
                "drug_name_guess": guess,
                "generic_name_guess": generic_guess,
                "dosage": item.get("dosage"),
                "frequency_or_timing_guess": item.get("frequency_or_timing_guess"),
                "confidence_notes": item.get("confidence_notes"),
                "suggested_vocab_matches": suggestions[:5],
            }
        )

    warnings = parsed.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    return {
        "source_guess": parsed.get("source_guess"),
        "date_guess": parsed.get("date_guess"),
        "medicines": normalized_medicines,
        "warnings": [str(warning) for warning in warnings],
    }
