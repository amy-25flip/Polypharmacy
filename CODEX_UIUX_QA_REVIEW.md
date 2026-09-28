Read-only static review completed across all requested files and Tailwind/Vite configuration. No files were modified.

## Blockers for a live demo

1. Removing a prescription can leave a stale interaction report on screen

   - Files: [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:47), especially [line 152](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:152)
   - Trigger: Run an interaction check, then remove one of several prescriptions. It is even worse if the removal occurs while screening is still running.
   - Experience: The combined medication list changes, but the previous report remains visible. An in-flight response for the deleted medicines can also still arrive and overwrite the page because this removal bypasses `updatePrescription()` and therefore does not increment `requestIdRef`.
   - Severity: **Blocker for a live demo**
   - Suggested fix: Route prescription removal through one centralized session-mutation helper that increments the request ID, clears `result` and `checkError`, and resets `isChecking`. Apply that helper to every mutation of `prescriptions`.

2. Opening Model Transparency silently destroys the current patient session

   - Files: [App.tsx](E:/Polypharmacy/webapp/frontend/src/App.tsx:46), [App.tsx](E:/Polypharmacy/webapp/frontend/src/App.tsx:62)
   - Trigger: Enter or scan medicines, click “Model transparency & real evaluation numbers,” then click “Back to checker” or use browser Back.
   - Experience: `PatientPrescriptionWorkflow` is unmounted while the transparency page is shown. Returning mounts a fresh workflow, so all prescriptions, timings, scan reviews, and results are gone without warning.
   - Severity: **Blocker for a live demo**
   - Suggested fix: Keep the workflow mounted and hide it while transparency is displayed, or lift its session state above the page switch. If preservation is intentionally impossible, warn before navigation—but preservation is the much safer behavior for this stateless per-visit workflow.

## High

3. Search failures are either invisible or can masquerade as “no database match”

   - Files: [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:44), [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:50)
   - Trigger: Search while `/api/drugs/search` is unavailable, times out, or returns an error.
   - Experience: The failure is written only to the developer console. Depending on whether the dropdown was already open, the doctor sees either nothing or the “No match found in database” fallback and may add a valid medicine as unverified. A service failure is therefore presented like a clinical-vocabulary result.
   - Severity: **High**
   - Suggested fix: Track a distinct search-error state, show an inline retryable error, close/suppress the unmatched fallback on request failure, and reserve “No match found” exclusively for a successful empty response.

4. Scan review has no duplicate protection, unlike text entry

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:108), [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:86), [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:160)
   - Trigger: Confirm a scanned medicine already present in that prescription, or confirm two OCR rows that resolve to the same normalized drug.
   - Experience: Text search warns that the drug is already added, while scan confirmation silently creates duplicate rows. The combined list later merges them, making the duplicate appear to disappear and potentially combining conflicting timings.
   - Severity: **High**
   - Suggested fix: Perform the same trim/case/whitespace-normalized duplicate check in the common add path, not only inside `DrugSearchInput`. Give scan rows explicit duplicate feedback and leave them pending for correction.

5. A mistaken scan confirmation or rejection cannot be corrected within the scan flow

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:165), [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:181), [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:207)
   - Trigger: Confirm the wrong suggested medicine, or accidentally press Reject.
   - Experience: The row becomes permanently disabled. For an incorrect confirmation, the main medication row allows timing changes but not name correction. The doctor must remove it and manually re-add it—or re-upload the entire image. An accidental rejection is similarly irreversible.
   - Severity: **High**
   - Suggested fix: Add an “Undo/Reopen” action for confirmed and rejected rows. Reopening a confirmed row should remove or update the linked session drug so scan state and medication state cannot diverge.

6. A successful scan with zero detected medicines produces no result state at all

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:89), [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:162)
   - Trigger: Gemini successfully returns `medicines: []`, with no useful warning.
   - Experience: The spinner simply disappears. There is no “No medicines detected,” no indication that the request completed successfully, and no direct instruction to retry with a clearer crop or use manual entry. This looks like a broken button during a demonstration.
   - Severity: **High**
   - Suggested fix: Render an explicit successful-empty state whenever `scan` exists and `rows.length === 0`, with the existing retry/manual-entry guidance. Similarly summarize when all rows are rejected or unconfirmable.

7. The autocomplete’s stale-request protection is incomplete

   - Files: [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:31)
   - Trigger: Type rapidly while an earlier request is completing or aborting.
   - Experience: `AbortController` is helpful, but an older request’s `finally` can set `isLoading(false)` after the newer request starts. If a response wins the narrow race before abort takes effect, it can briefly install suggestions for the previous query, and a fast Enter/click can add the wrong suggestion.
   - Severity: **High**
   - Suggested fix: Add a monotonically increasing search request ID, and apply suggestions, errors, dropdown state, and loading completion only when the response belongs to the latest query. Keep `AbortController` as an additional optimization.

## Medium

8. Scan-derived source and date are discarded even though the workflow asks for prescription provenance

   - Files: [client.ts](E:/Polypharmacy/webapp/frontend/src/api/client.ts:154), [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:89), [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:138)
   - Trigger: Scan an image from which Gemini returns `source_guess` or `date_guess`.
   - Experience: Neither value is displayed or offered to the doctor; the prescription remains generically labelled unless the doctor separately notices and edits the source field. Manual and scanned provenance therefore behave inconsistently.
   - Severity: **Medium**
   - Suggested fix: Display the extracted source/date for review and offer a deliberate “Use as prescription label” action, or pass a reviewed label suggestion to the parent. Do not silently overwrite a label the doctor has already edited.

9. Long medication names are visually hidden in the editable list

   - Files: [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:174)
   - Trigger: Add a long generic/combination name, especially on a narrow screen.
   - Experience: The name is forced into a three-column row beside timing and delete controls and rendered with `truncate`. Clinically distinguishing suffixes can disappear, with no title, expansion, or visible full-name affordance.
   - Severity: **Medium**
   - Suggested fix: Stack the timing/remove controls below the name at the smallest breakpoint, allow the name to wrap with `break-words`, and optionally expose the full value in a tooltip/title. Avoid relying on truncation for clinical identifiers.

10. Several scan and results rows can overflow at phone width

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:208), [SubsetCertificateView.tsx](E:/Polypharmacy/webapp/frontend/src/components/SubsetCertificateView.tsx:48), [SubsetCertificateView.tsx](E:/Polypharmacy/webapp/frontend/src/components/SubsetCertificateView.tsx:69), [Header.tsx](E:/Polypharmacy/webapp/frontend/src/components/Header.tsx:18)
   - Trigger: Use a roughly 320-pixel viewport, especially with long drug names.
   - Experience:
     - “Confirm this medicine” and “Reject” share a non-wrapping flex row inside several nested padded containers.
     - Certificate drug combinations and percentages use `justify-between` without shrink/wrap safeguards.
     - The PolyGuard title and long “Clinical Decision Support” badge occupy a non-wrapping heading row.
   - Severity: **Medium**
   - Suggested fix: Use `flex-wrap` or responsive column layouts, add `min-w-0` to text containers, and apply `break-words`/`overflow-wrap:anywhere` to drug-name content.

11. Results appear far below the action without a focus or scroll handoff

   - Files: [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:233), [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:253)
   - Trigger: Check a large regimen, particularly after entering several prescriptions or scanned rows.
   - Experience: The loading label stops, but the newly rendered report is below the combined list and full timing overview. A sighted user may not notice the result appeared; a keyboard or screen-reader user is left at the button with no programmatic movement to the result heading.
   - Severity: **Medium**
   - Suggested fix: Give the results heading/container a ref and `tabIndex={-1}`, then focus it and optionally `scrollIntoView` after the current request succeeds. Announce errors and completion through an appropriate live region.

12. The autocomplete does not expose full combobox semantics to assistive technology

   - Files: [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:158), [DrugSearchInput.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugSearchInput.tsx:199)
   - Trigger: Complete drug entry with a screen reader.
   - Experience: The input is associated with a visible label and custom arrow-key handling, but lacks `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-autocomplete`, and `aria-activedescendant`. Screen readers may not announce the popup, result count, or highlighted option. Duplicate feedback is also not live-announced.
   - Severity: **Medium**
   - Suggested fix: Implement the ARIA combobox pattern with stable option IDs. Put search status, errors, and duplicate feedback in a restrained `aria-live="polite"` region.

13. Backend health failure is displayed indefinitely as “Connecting…”

   - Files: [App.tsx](E:/Polypharmacy/webapp/frontend/src/App.tsx:35), [Header.tsx](E:/Polypharmacy/webapp/frontend/src/components/Header.tsx:30)
   - Trigger: Initial health request fails.
   - Experience: Both initial loading and failure use `knownDrugsCount === null`, so the header continues to say “Connecting to database...” forever. It never tells the presenter that the connection failed.
   - Severity: **Medium**
   - Suggested fix: Model health as separate `loading`, `ready`, and `error` states. Show a concise unavailable/error status on failure, without using a green activity icon.

14. Re-selecting the same scan image may do nothing after failure

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:134)
   - Trigger: Select an image, receive a scan failure or unsatisfactory result, then choose that exact same file again.
   - Experience: The file input value is never cleared. Browsers commonly do not fire `change` when the identical file is selected, so the retry appears unresponsive.
   - Severity: **Medium**
   - Suggested fix: Clear `event.currentTarget.value` after capturing the `File`, or reset it when the scan completes/fails.

15. Print pagination rules are risky for large regimens

   - Files: [index.css](E:/Polypharmacy/webapp/frontend/src/index.css:28), [InteractionResults.tsx](E:/Polypharmacy/webapp/frontend/src/components/InteractionResults.tsx:273)
   - Trigger: Print/export a regimen with 10 medicines and therefore up to 45 pair cards.
   - Experience: Global `section { break-inside: avoid; }` applies to the entire pair-by-pair section, which cannot fit on one page. Browser handling of an oversized unbreakable section varies and can create large blank areas or awkward clipping/pagination.
   - Severity: **Medium**
   - Suggested fix: Do not prohibit breaks on the pair-review parent section. Keep `break-inside: avoid` on individual pair `article` cards and compact report blocks only.

## Low

16. Scan status changes and loading are not consistently announced

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:131), [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:168)
   - Trigger: Scan, confirm, or reject using a screen reader.
   - Experience: Visible labels change, but there is no `aria-live`/status announcement for “Reading,” results ready, or row status changes.
   - Severity: **Low**
   - Suggested fix: Add a concise `role="status"` region for scan progress/completion and ensure confirmed/rejected state changes are announced.

17. Confirming an OCR-edited name does not show whether it matched the vocabulary

   - Files: [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx:108), [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:160)
   - Trigger: Replace an OCR suggestion with a free-typed name and confirm it.
   - Experience: Unlike the manual path, it is added without `isUnmatched`, so the prescription row provides no immediate “not matched” warning. Only the later backend report may reveal exclusion.
   - Severity: **Low**
   - Suggested fix: Validate confirmed scan names against the provided vocabulary matches or a lookup before addition, and pass the same matched/unmatched status used by manual entry.

18. The empty timing overview adds substantial inactive UI before any medicine exists

   - Files: [MedicationTimingTable.tsx](E:/Polypharmacy/webapp/frontend/src/components/MedicationTimingTable.tsx:24), [PatientPrescriptionWorkflow.tsx](E:/Polypharmacy/webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx:251)
   - Trigger: Open a new session with no medicines.
   - Experience: Six “None listed” groups are shown despite having nothing to summarize, making the initial workflow longer and pushing future results farther down.
   - Severity: **Low**
   - Suggested fix: Hide the timing overview until at least one medicine exists, or show a single compact empty state.

19. `DrugChipList` is obsolete and inconsistent with the actual workflow

   - Files: [DrugChipList.tsx](E:/Polypharmacy/webapp/frontend/src/components/DrugChipList.tsx:1)
   - Trigger: Not currently reachable; the component is unused.
   - Experience: It implements a second medication-list vocabulary and interaction pattern without timing support. Reusing it later would reintroduce the exact cross-flow inconsistency just fixed.
   - Severity: **Low**
   - Suggested fix: Remove it if genuinely obsolete, or refactor it to consume the shared session-medication model and timing controls before reuse.

## Genuinely solid

- Text entry now exposes timing before addition and deliberately preserves that timing for rapid same-schedule entry.
- The common combined list normalizes case and repeated whitespace across prescriptions and preserves multiple sources/timings.
- The interaction-check request-ID guard correctly prevents most edited-session/stale-response overwrites.
- Scan extraction requires explicit per-item review rather than silently trusting OCR.
- The disabled screening button clearly says “Add at least 2,” with an additional explanation after the first medicine.
- Severity is not communicated by color alone: banners, badges, text labels, icons, and explicit uncertainty/abstention wording are present.
- Unmatched medicines, inferred results, evidence limits, and model abstention are described honestly rather than presented as false certainty.
- Buttons and editable controls generally have useful accessible names, and the global focus-visible styling is appropriate.
- Long pair names use `break-words` in the primary pair review, and the transparency comparison table sensibly permits horizontal scrolling.
- Print/export controls, report disclaimer, print-only heading, and per-pair article structure are strong foundations once the parent pagination rule is corrected.