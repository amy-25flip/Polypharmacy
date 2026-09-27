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

from brand_names import BRAND_NAMES, lookup_brand_name


NOT_CONFIGURED_ERROR = (
    "Prescription scanning is not configured on this server (GEMINI_API_KEY not set)."
)


def _build_brand_reference() -> str:
    """A compact brand -> generic reference block, built once at import time
    from the same curated Indian brand-name index used for post-hoc matching
    (webapp/brand_names.py). Giving Gemini this as context while it reads,
    not just matching against it afterward, should help it recognize a
    partially-legible brand name it might otherwise misread - but it must
    never be used to force a match onto handwriting that does not actually
    resemble one of these (see the caveat at the end of the prompt)."""
    lines = [f"{brand} -> {', '.join(generics)}" for brand, generics in sorted(BRAND_NAMES.items())]
    return "\n".join(lines)


_BRAND_REFERENCE = _build_brand_reference()

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
      "confidence_notes": "brief uncertainty note or null",
      "bounding_box": {
        "y_min": "number from 0 to 1000",
        "x_min": "number from 0 to 1000",
        "y_max": "number from 0 to 1000",
        "x_max": "number from 0 to 1000"
      }
    }
  ],
  "warnings": ["any image-quality, handwriting, ambiguity, or completeness warnings"]
}
If no medicine can be read, return an empty medicines list and explain why in warnings.
Every field must be present. This output will be reviewed by a doctor and must not
be described as verified. Set generic_name_guess to null when drug_name_guess
already appears to be a generic name or when there is no reasonable ingredient guess.
Never invent or autocomplete an uncertain medicine name merely because it looks
plausible. If the medicine name is not reasonably legible, set drug_name_guess to
an empty string or "illegible" and clearly describe the uncertainty in
confidence_notes and/or warnings. For each medicine, return bounding_box around
that medicine's visible text using Gemini's normalized 0-1000 coordinates in
y_min, x_min, y_max, x_max order. Set bounding_box to null if you cannot localize it.

Reference only - common Indian brand-name medicines and their generic
ingredient(s), which may help you recognize a partially-legible brand name:
{brand_reference}
This list is not exhaustive and the medicine written may not be on it at all.
Never force a match to this list - only use it if the handwriting genuinely
resembles one of these names. It does not override the anti-guessing rule above.
""".strip().replace("{brand_reference}", _BRAND_REFERENCE)


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


def _normalize_bounding_box(value: Any) -> dict[str, float] | None:
    """Accept a valid normalized box and silently discard malformed model output."""
    if isinstance(value, dict):
        coordinates = [value.get(key) for key in ("y_min", "x_min", "y_max", "x_max")]
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        coordinates = list(value)
    else:
        return None

    if any(isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)) for coordinate in coordinates):
        return None
    y_min, x_min, y_max, x_max = (float(coordinate) for coordinate in coordinates)
    if not (0 <= y_min < y_max <= 1000 and 0 <= x_min < x_max <= 1000):
        return None
    return {"y_min": y_min, "x_min": x_min, "y_max": y_max, "x_max": x_max}


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
                "bounding_box": _normalize_bounding_box(item.get("bounding_box")),
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
