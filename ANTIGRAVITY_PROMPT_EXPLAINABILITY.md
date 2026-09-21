Add an "explainability" display to the already-built PolyGuard frontend at `E:\Polypharmacy\webapp\frontend\`. This is a small, additive change — do not restructure the existing components, just extend them. The backend (`E:\Polypharmacy\webapp\main.py`) is already updated and live at `http://127.0.0.1:8765` — verify the new field with the curl example below before building.

## What changed in the API

Each object inside `regimen.pairs[]` from `POST /api/check` now *optionally* carries an `explanation` field. It is only present when that pair's severity is `"Moderate"` or `"Major"` — Minor-severity pairs never have it, so no UI is needed for those (same as today).

Real example response (Metformin + Furosemide, live right now):
```json
{
  "drug_a": "Metformin",
  "drug_b": "Furosemide",
  "severity": "Moderate",
  "confidence": 0.963,
  "explanation": {
    "has_explanation": true,
    "primary_reason": {
      "type": "side_effect",
      "title": "Shared adverse-effect evidence",
      "plain_text": "Both medicines are linked to overlapping effects (Abdominal bloating, Epigastric discomfort, Lightheadedness), so combining them may increase that risk.",
      "evidence": ["Abdominal bloating", "Epigastric discomfort", "Lightheadedness"]
    },
    "supporting_evidence": [
      { "type": "class", "items": ["Antithrombotic agent"] }
    ],
    "coverage": { "drug_a_has_kg_data": true, "drug_b_has_kg_data": true },
    "caveat": "This is knowledge-graph evidence, not a confirmed patient-specific mechanism."
  }
}
```

`primary_reason.type` is one of `"class"`, `"side_effect"`, or `"gene"`. `supporting_evidence` is an array of `{ type, items: string[] }` and can be empty. When no knowledge-graph overlap was found at all (still possible even on a Moderate/Major pair — coverage isn't 100%), the shape is:
```json
{
  "has_explanation": false,
  "primary_reason": null,
  "supporting_evidence": [],
  "coverage": { "drug_a_has_kg_data": true, "drug_b_has_kg_data": false },
  "caveat": "This is knowledge-graph evidence, not a confirmed patient-specific mechanism."
}
```

Verify live: `curl -s -X POST http://127.0.0.1:8765/api/check -H "Content-Type: application/json" -d '{"drugs":["Metformin","Furosemide"]}'`

## Where to update

1. `src/api/client.ts` — extend the `InteractionPair` type with the optional `explanation` field (mirror the JSON shape above exactly).
2. `src/components/InteractionResults.tsx` — this is the only component that needs new UI. Two places to add it:
   - **Under the "Highest-risk interaction" callout** (the one already shown right under the main severity banner): if `highestRiskPair.explanation` is present, show its content directly there — this is the most important placement, since most doctors won't open "Show all interactions."
   - **Inside each row of the existing "Show all interactions" table**: when a row's pair has an `explanation`, make the row expandable (or add a small "why" indicator/icon that reveals the explanation inline) so doctors can check the reason for any pair, not just the worst one.

## Exact display rules

- **`has_explanation: true`**: show `primary_reason.plain_text` as the main sentence — that's already written in full plain language, use it directly, don't rephrase it. Below it, in smaller/quieter text, show `primary_reason.title` as a label and list `primary_reason.evidence` items (e.g. "Evidence: Abdominal bloating, Epigastric discomfort, Lightheadedness"). If `supporting_evidence` is non-empty, show it further below under a smaller heading like "Additional evidence" — each item as `type` (turn `"class"` → "Shared drug class", `"side_effect"` → "Shared adverse-effect", `"gene"` → "Shared biological target", `"structural_resemblance"` → "Structural similarity") followed by its `items` list.
- **`has_explanation: false`**: still show *something*, calmly — never leave a blank gap where the explanation would be (a missing explanation on a flagged risky pair looks broken, not absent). Use exactly this framing: "No specific shared-mechanism evidence was found in the current knowledge base for this pair. This may reflect incomplete data coverage rather than an absence of risk." If `coverage.drug_a_has_kg_data` or `drug_b_has_kg_data` is `false`, you can optionally add a small note like "Limited reference data available for one of these medicines."
- **Always show `caveat`** somewhere near the explanation content, small/muted text — it's short and important: "This is knowledge-graph evidence, not a confirmed patient-specific mechanism."
- **Section label**: don't call this "AI explanation" or "model reasoning" anywhere. Call it something like "Possible mechanism" or "Why this may be risky" — a heading, not a claim of certainty.

## Tone constraints (same audience as before — low-tech-literacy doctors)

- Never use the words "causes", "proves", "confirmed", or "exact reason" anywhere in this UI — the module intentionally only claims *association/evidence*, not certainty. The `plain_text` strings already follow this (they say "may increase", "may contribute", "linked to") — don't add stronger language around them.
- Gene/target names (e.g. "CYP3A5") are real but technical — it's fine to show them as supporting evidence/detail, just don't make them the only thing shown; `primary_reason.plain_text` always has the plain-language framing first.
- Keep the same visual language already established elsewhere in the app (the existing color system, card/section styling, no new component library).
