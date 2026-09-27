# PolyGuard live-demo risk review

> Unable to create the requested output file because the workspace is read-only. No files were modified and no git commands were run.

1. **Prescription scanning has never completed a successful live extraction** — `PRESCRIPTION_WORKFLOW_IMPLEMENTATION_SUMMARY.md:50`, `webapp/prescription_scan.py:149-156`  
   **Trigger:** Upload a prescription image during the demo. The documented five live attempts all returned Gemini `503 UNAVAILABLE`; there is no confirmed successful response against the currently configured `gemini-3.8-flash` model. The SDK call also has no explicit timeout, so it may leave the interface spinning during an outage.  
   **Severity:** **High — likely visible demo failure.** The UI degrades gracefully instead of crashing, but the headline scanning feature may simply fail or stall. This should not be demonstrated tomorrow without a successful pre-demo smoke test on the same machine/key/network.

2. **Corrupted control/replacement characters are visibly rendered in several prominent UI strings** — `webapp/frontend/src/App.tsx:68`, `webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:188`, `webapp/frontend/src/components/PrescriptionScanReview.tsx:204`, `webapp/frontend/src/components/TransparencyPage.tsx:198`  
   **Trigger:** Open the checker/footer, view a combined medication row, view OCR dosage/timing details, or open the transparency page. The source contains U+0007 or `�` where separators should appear.  
   **Severity:** **High embarrassment / low functional impact.** These can appear as boxes, missing glyphs, or `�`, making the product look encoding-corrupted during ordinary walkthroughs.

3. **The scanner does not fully normalize Gemini’s field types before returning them** — `webapp/prescription_scan.py:206-208`, `webapp/frontend/src/components/PrescriptionScanReview.tsx:55-56,90-96`  
   **Trigger:** Gemini returns valid JSON but emits a number, array, or object for `frequency_or_timing_guess` instead of a string—plausible for unconstrained model output. The backend passes it through; the frontend calls `.toLowerCase()` and throws while constructing review rows.  
   **Severity:** **Medium-high — visible feature failure.** The surrounding request handler catches the exception, so the entire app does not blank, but a successful HTTP scan is misleadingly shown as “Prescription scanning failed.” The client type promises `string | null`, which the backend does not enforce.

4. **There is no regimen-size limit despite quadratic pair evaluation and synchronous model work** — `webapp/main.py:276-281,365-377`, `webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:44-48,169-175`  
   **Trigger:** Add many medicines or prescriptions and click “Check interactions.” Ten medicines require 45 pair evaluations; 20 require 190. Each pair invokes the primary model, conformal engine, explanation lookup, evidence passport, and potentially the chemistry model. The UI permits unlimited additions.  
   **Severity:** **Medium — possible hang/time-out during an exploratory demo.** Normal 2–5-drug examples should be fine, but a reviewer testing “polypharmacy” with a large list can visibly stall the request.

5. **Nominally auxiliary evidence features can prevent the entire API from starting** — `webapp/main.py:68-106`, `webapp/brand_names.py:13-18`, `webapp/evidence_passport.py:21-29`, `webapp/disagreement_sentinel.py:40-48`, `webapp/conformal.py:24-29`  
   **Trigger:** Start the backend with any model, vocabulary, brand-name, calibration, chemistry, conformal, or explanation artifact missing/corrupt, or without RDKit/import dependencies. Every component is imported and loaded eagerly; none of the optional evidence engines degrades independently. Even `/api/health` becomes unavailable.  
   **Severity:** **Medium operational risk, catastrophic if triggered.** All expected artifacts currently exist in this checkout, so it should start in this exact environment. However, this contradicts the “safe module wiring” characterization in `PRESCRIPTION_WORKFLOW_IMPLEMENTATION_SUMMARY.md:20` and makes last-minute copying/deployment fragile.

6. **Prescription uploads have no size limit and are read wholly into memory** — `webapp/main.py:350-359`  
   **Trigger:** Select a very large phone photograph or malformed image file carrying an `image/*` MIME type. The server reads the complete upload before calling Gemini; it does not validate image decoding, dimensions, or byte size.  
   **Severity:** **Low-medium — possible slow/failing scan.** Ordinary photographs should work, and Gemini errors are caught, but an unusually large image can consume memory or make the live scan noticeably slow.

No current backend/client response-shape mismatch was found for `/api/check`, search, health, or the normal well-formed prescription-scan response. Empty lists, one recognized drug, Unicode/unknown names, malformed JSON from Gemini, and malformed bounding boxes are handled without a blank-screen crash. The research documents are broadly coherent with the deployed model and candid about negative results; the main credibility concern is the explicitly unvalidated successful OCR path noted above.