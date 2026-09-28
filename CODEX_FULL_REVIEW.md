## Blocker

1. **[webapp/main.py:406](E:/Polypharmacy/webapp/main.py:406) — blocker.** The SPA fallback joins untrusted `full_path` directly onto `frontend/dist`, and an encoded `..` request successfully returned `webapp/.env`—including the Gemini key—through the public FastAPI/ngrok server. **Fix:** resolve the candidate path and require `candidate.is_relative_to(_FRONTEND_DIST.resolve())`, or serve static files only through `StaticFiles` and make the catch-all always return `index.html`; rotate the current Gemini key after fixing this.

## High

2. **[webapp/main.py:300](E:/Polypharmacy/webapp/main.py:300), [webapp/main.py:365](E:/Polypharmacy/webapp/main.py:365) — high.** `/api/check` has no list-size, string-length, uniqueness, or request-cost limit, so a malformed/public request containing hundreds of repeated valid drugs triggers quadratic pair prediction and potentially stalls the demo server. **Fix:** constrain the Pydantic model—such as 2–10 drugs and bounded nonblank names—normalize/deduplicate before prediction, and reject oversized requests with 422/400.

3. **[webapp/main.py:350](E:/Polypharmacy/webapp/main.py:350), [webapp/prescription_scan.py:162](E:/Polypharmacy/webapp/prescription_scan.py:162) — high.** The scan endpoint reads an unlimited upload into memory and then makes a synchronous, timeout-free Gemini call inside an `async` route, allowing a large or slow request to consume memory and freeze health, search, and interaction requests. **Fix:** enforce a conservative byte/pixel limit, verify actual image content, configure an explicit Gemini timeout/retry policy, and execute the blocking SDK call in a worker thread or make the route synchronous.

4. **[start_polyguard.ps1:71](E:/Polypharmacy/start_polyguard.ps1:71) — high.** The launcher interpolates `GEMINI_API_KEY` into a child PowerShell `-Command` argument, exposing the secret in process command-line inspection and creating quoting/injection risk. **Fix:** pass an environment dictionary to `Start-Process`, or launch through a small wrapper that inherits a safely prepared environment without embedding the key in command text.

5. **[PatientPrescriptionWorkflow.tsx:67](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:67) — high.** If the user changes or removes medication while `/api/check` is running, the old promise can later overwrite cleared state and display results for the previous regimen. **Fix:** snapshot/version each request or use an `AbortController`, and only apply the response when its version still matches the current combined medication list.

## Medium

6. **[webapp/main.py:68](E:/Polypharmacy/webapp/main.py:68), [webapp/brand_names.py:16](E:/Polypharmacy/webapp/brand_names.py:16) — medium.** Every primary and optional feature artifact is loaded eagerly without isolation, so one missing/corrupt conformal, disagreement, explainability, HODDI, CSV, brand, or joblib file prevents the entire application—including `/api/health` and the frontend—from starting. **Fix:** fail fast only for the indispensable pairwise model/vocabulary, load optional engines independently with schema validation, and return explicit “feature unavailable” fields when an auxiliary artifact fails.

7. **[webapp/prescription_scan.py:171](E:/Polypharmacy/webapp/prescription_scan.py:171) — medium.** Raw Gemini/SDK exception text is placed in the API response and rendered by the frontend, potentially exposing provider internals, request metadata, or sensitive diagnostics to public users. **Fix:** log a sanitized server-side exception with a request ID and return a stable generic message, distinguishing timeout, quota, and temporary-provider failures without echoing `exc`.

8. **[webapp/main.py:367](E:/Polypharmacy/webapp/main.py:367) — medium.** Direct API requests containing duplicate recognized names produce self-pairs such as `Warfarin + Warfarin` and duplicate resolved IDs in the HODDI/subset models, yielding clinically meaningless output. **Fix:** normalize and deduplicate while preserving order before creating `matched`, and report duplicates separately if the UI needs to explain their removal.

9. **[InteractionResults.tsx:44](E:/Polypharmacy/webapp/frontend/src/components/InteractionResults.tsx:44) — medium.** The headline’s uncertainty state is derived only from the first sorted pair, so an abstained top-confidence Major pair can hide another reliable Major result, while an abstained non-first pair is omitted from the overall uncertainty summary. **Fix:** compute the banner from all pairs—surface the highest reliable severity and separately state whether any pairs abstained.

10. **[webapp/main.py:352](E:/Polypharmacy/webapp/main.py:352) — medium.** Upload validation trusts the caller-supplied `Content-Type`, meaning arbitrary bytes labeled `image/*` are sent to Gemini and may produce avoidable failures or cost. **Fix:** decode the image with a trusted library, reject unsupported/corrupt formats, strip metadata where appropriate, and send the detected MIME type.

## Low

11. **[webapp/main.py:368](E:/Polypharmacy/webapp/main.py:368) — low.** Vocabulary matching is case- and whitespace-normalization-sensitive even though search and documentation lookup are normalized, so a valid direct API input such as differently cased drug text is silently classified as unmatched. **Fix:** maintain a normalized-name-to-canonical-name map and canonicalize submitted names before matching.

12. **[webapp/prescription_scan.py:231](E:/Polypharmacy/webapp/prescription_scan.py:231) — low.** `source_guess` and `date_guess` remain raw Gemini values rather than using the same defensive string coercion as other fields, leaving the response inconsistent with the declared frontend type if those fields are later displayed. **Fix:** pass both through `_coerce_optional_str`.

13. **[PrescriptionScanReview.tsx:77](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:77) — low.** Scan requests cannot be aborted on component unmount or replacement, so removing a prescription during OCR wastes the external request and may attempt state updates after unmount. **Fix:** accept an `AbortSignal` in `scanPrescription`, abort in cleanup, and ignore stale results.

## Looks solid

- The critical prompt-template regression is fixed correctly: `.replace("{brand_reference}", ...)` is safe with the literal JSON braces in the prompt.
- Missing `GEMINI_API_KEY` degrades to a structured 503 without preventing backend startup.
- Gemini medicine fields, warnings, and bounding boxes are generally normalized defensively; invalid boxes are discarded.
- React renders server/Gemini strings as escaped text—no `dangerouslySetInnerHTML` or equivalent XSS sink was found.
- Drug-search requests are debounced and aborted correctly.
- CORS is restricted to configured origins/local development and does not permit credentials.
- `.env`, `*.env`, and `*.log` are gitignored while `.env.example` remains tracked. The two current logs contain no API-key-like values or email addresses in the checks performed.
- The current local artifacts all exist, backend import completed successfully, and the built frontend contains the new print-report code.
- The print button and `print:hidden` usage are wired correctly, and the frontend suite passes: **7 test files, 22 tests**.