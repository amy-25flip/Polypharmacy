Build the frontend for **PolyGuard**, a medication interaction checker. The backend (a FastAPI JSON API) is already built and lives at `E:\Polypharmacy\webapp\main.py` — do not modify it. Build the frontend as a separate app at:

```
E:\Polypharmacy\webapp\frontend\
```

It should run standalone (its own dev server, e.g. Vite) and talk to the backend at `http://127.0.0.1:8765` over fetch/JSON (port 8000 is blocked on this machine by Windows, so the backend runs on 8765 instead — verify by hitting `http://127.0.0.1:8765/api/health`, it should return `{"status":"ok","known_drugs":1902}`). The backend has CORS wide open for local dev.

## Audience — read this first, it drives every UI decision

End users are **doctors with very low tech literacy**, using this in seconds during a real patient consultation. This is not a dashboard, not a data-science tool, not something with a "cool AI product" feel. It should feel like a fast, calm clinical calculator. No jargon, no visible model internals (no "TF-IDF", "confidence score", "probability", "neural network", "AUROC" anywhere in the UI), no clutter.

## Backend API contract (already implemented, tested against these shapes)

**`GET /api/health`**
```json
{ "status": "ok", "known_drugs": 1902 }
```

**`GET /api/drugs/search?q=metf`** — fuzzy autocomplete, call this as the doctor types (debounce ~200ms, only fire once `q.length >= 2`)
```json
["Metformin", "Metformin hydrochloride", "Metolazone"]
```
Returns `[]` if no matches or query too short. Plain array of drug name strings — these are the *only* valid values to send back in `/api/check`.

**`POST /api/check`** — body:
```json
{ "drugs": ["Metformin", "Warfarin", "Aspirin"] }
```
Response:
```json
{
  "entered": ["Metformin", "Warfarin", "Aspirin"],
  "matched": ["Metformin", "Warfarin", "Aspirin"],
  "unmatched": [],
  "regimen": {
    "overall_severity": "Major",
    "pairs": [
      { "drug_a": "Warfarin", "drug_b": "Aspirin", "severity": "Major", "confidence": 0.91 },
      { "drug_a": "Metformin", "drug_b": "Warfarin", "severity": "Moderate", "confidence": 0.77 },
      { "drug_a": "Metformin", "drug_b": "Aspirin", "severity": "Minor", "confidence": 0.65 }
    ]
  },
  "combination_signal": {
    "drugs_used": 3,
    "drugs_total": 3,
    "probability": 0.82,
    "elevated": true
  }
}
```
Notes on this response:
- `overall_severity` is one of `"Minor"`, `"Moderate"`, `"Major"`, or `null` if fewer than 2 matched drugs were entered.
- `pairs` is sorted worst-first — `pairs[0]` is always the highest-risk pair (that's what drives the overall banner).
- `unmatched` lists any entered drug names the backend didn't recognize (this shouldn't normally happen if the frontend only lets doctors pick from `/api/drugs/search` results, but handle it defensively anyway).
- `combination_signal` is `null` whenever fewer than 3 matched drugs were entered, or too few of the entered drugs have data for this deeper check. When present, `elevated: true/false` is the only thing that should drive UI framing — don't show the raw `probability` number to the user (see framing rules below).

## Required UX flow

**Screen 1 — medication entry**
1. A short, calm safety line visible at the top, always, not hidden in a footer:
   > "PolyGuard is a clinical decision-support tool. It helps flag possible interaction risks and does not replace clinical judgment, prescribing guidelines, or pharmacist review."
2. One search box: `Add medicine`. As the doctor types 2+ letters, show a dropdown of matches from `/api/drugs/search`. Selecting one adds it as a removable chip/tag below the box (e.g. `Metformin ✕`). Clicking the ✕ removes it.
3. Do **not** let doctors free-type and submit arbitrary text as a drug — they must pick from the suggested list, or explicitly add an unmatched item (see below).
4. If a doctor types something with no good matches, show a clear, non-blocking option like "No match found — add 'Azithromicin' anyway?" so they aren't stuck, but the item is visually marked as unmatched (e.g. a gray/dashed chip) and the result screen will say it couldn't be checked.
5. A single primary button: `Check interactions` — disabled/inactive until at least 2 medicines are added.

**Screen 2 (or an in-place result panel) — result**
1. One dominant banner at the top showing the overall result, color-coded:
   - Green — no matched pairs at Moderate/Major (i.e. `overall_severity` is `"Minor"` or `null` with no risky pairs)
   - Amber — `overall_severity === "Moderate"`
   - Red — `overall_severity === "Major"`
   - Gray — fewer than 2 matched drugs (incomplete check)
   Show the plain-language severity word (Minor/Moderate/Major) prominently, not a number or score.
2. Directly under the banner, name the specific highest-risk pair in plain text: "Highest-risk interaction: Warfarin + Aspirin."
3. A collapsed/expandable "Show all interactions" section listing every pair from `regimen.pairs`, each with its own severity color — collapsed by default so it doesn't clutter the primary view.
4. If `unmatched` is non-empty, a clearly visible (not buried) note: "N medicine(s) could not be checked: X, Y" — framed as a limitation, not an error.
5. If `combination_signal` is present and `elevated === true`, show a **secondary**, visually distinct (smaller/quieter than the main banner) note:
   > "Combination pattern check: this combination resembles known higher-risk medication patterns. Use this as a review prompt, not a confirmed interaction."
   If `combination_signal` is `null` or `elevated === false`, show nothing extra for it — do not display "not elevated" as if it were a clean bill of health, since it's a supplementary signal, not a primary result.
6. Never combine `regimen.overall_severity` and `combination_signal` into one single fused score. They answer different questions and must stay visually/conceptually separate — the severity banner is the primary answer, the combination note (when shown) is a secondary prompt.
7. A restrained action-oriented line under a Major result specifically: "Review therapy, dose, alternatives, or monitoring needs before continuing."

## Visual/tone constraints
- Large, high-contrast text; this may be used on a phone or a clinic desktop with older monitors — don't assume a big high-res display.
- Minimal steps: search → pick → repeat → one button → result. No multi-page wizards, no account creation, no settings screen needed for v1.
- No model names, confidence percentages, or ML terminology anywhere in the doctor-facing UI.
- Keep the color system consistent: green/amber/red/gray as defined above, used nowhere else for unrelated meanings.

## Tech expectations
- Any modern frontend stack is fine (plain JS, React, Svelte, whatever Antigravity defaults to) — simplicity and reliability matter more than framework choice.
- Must run as a standalone dev server and call the backend via `fetch` at `http://127.0.0.1:8765` (this is already running and tested — confirm with `GET http://127.0.0.1:8765/api/health` before building against it).
- No build step should require internet access to the FastAPI backend at build time — it only needs the backend running at *runtime* for the API calls.
