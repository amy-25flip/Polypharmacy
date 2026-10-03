# Doctor-facing diagnosis plan: frontend handoff

## Files changed

- `webapp/frontend/src/api/client.ts` — typed disease, reference medicine, and candidate screening API calls with `AbortSignal` support.
- `webapp/frontend/src/components/PatientPrescriptionWorkflow.tsx` — diagnosis groups in the existing session model; combined plan screening, whole-plan panel, error/retry, request guards, and print data flow.
- `webapp/frontend/src/components/DiseaseCombobox.tsx` — new searchable, keyboard-operable diagnosis combobox.
- `webapp/frontend/src/components/DiagnosisMedicinePicker.tsx` — new browse/filter/multi-select picker with live candidate flags.
- `webapp/frontend/src/components/ScreeningFlag.tsx` — reusable severity, uncertainty, and adverse-effect details display.
- `webapp/frontend/src/components/DrugSearchInput.tsx` — unique ARIA IDs for multiple search inputs in one plan.
- `webapp/frontend/src/components/InteractionResults.tsx` — print-only medication plan by diagnosis block in the report header.
- `webapp/frontend/src/__tests__/DiagnosisPlan.test.tsx` — mocked integration tests for the diagnosis workflow and screening races.
- `webapp/frontend/package.json` — Vite build uses `--configLoader native` because the default config loader failed on this Windows installation with `spawn EPERM`; TypeScript and Vite output are unchanged.

## Component and state flow

`PatientPrescriptionWorkflow` owns one array of groups. Each group has `kind: 'prescription' | 'diagnosis'`; diagnosis groups also store a disease ID and fixed disease-name label. The existing merge-by-name calculation produces one combined medication list with all source labels. Existing timing, check, results, reset, and print flows consume this same list.

`DiseaseCombobox` searches on focus and query changes. Selecting a disease adds one diagnosis group. `DiagnosisMedicinePicker` loads that disease's reference medicines, filters locally, and toggles medicines through the workflow's existing add/remove paths. The free-text medicine search remains in every group.

Each picker reports its visible unselected medicines to the workflow. After a 300 ms debounce, the workflow sends the deduplicated selected names and up to 100 candidates to `/api/screen-candidates`. Its request ID and `AbortController` discard superseded responses. Edits clear old flags immediately. The response supplies candidate row flags and the selected-summary pairs used by the combined-list rows and whole-plan panel. A failed request shows an explicit error and Retry, with no no-flag badges. Prescription-only sessions do not call this new endpoint.

## Contract assumptions and limits

- The API returns disease search results in the documented order; the combobox does not reorder them. It expects disease IDs to be stable.
- Candidate names and pair names are matched case-insensitively to display rows. The backend supplies canonical medicine names and severity strings from the agreed JSON contract.
- `adverse_effect_basis` is rendered verbatim wherever adverse effects are shown in this feature. An unmatched medicine is labeled unknown, not no-flag.
- The API accepts at most 100 selected names and 100 candidates. Candidates beyond the first 100 visible unselected names across all diagnosis pickers are not screened and receive an explicit limited-screening message. More than 100 selected medicines produce an error instead of a partial whole-plan estimate.
- “Safest first” and “Hide Major interactions” use only the latest successful screen response. The default view remains alphabetical with nothing hidden.
- The backend endpoints were still being built during frontend implementation. No real-backend response or mobile browser session was available for verification; the tests use mocked API calls.

## Verification

- `npm test -- --run`: **7 test files, 33 tests passed**.
- `npm run build`: **passed** (`tsc -b` and Vite production build; 1,892 modules transformed).

## Manual test with the real backend

1. Open the existing app at a 375 px viewport. Add a diagnosis, focus the search field, confirm the full list loads, type `diabetes`, and select it with Arrow Down/Enter. Search it again and confirm the duplicate message.
2. In the Diabetes card, browse, filter, select two medicines, then unselect one. Confirm the card, combined list, timing overview, and check-button count change together. Add a free-text medicine in the same card.
3. Add a second diagnosis, such as kidney disease. Tick a medicine already selected under Diabetes. Confirm it appears once in the combined list with both `From:` sources and once in the screening request's selected array.
4. Select a medicine that has a documented or inferred interaction. Check the candidate row's severity, `with` medicine, details, adverse-effect chips, verbatim basis sentence, and any low-confidence marker. Confirm an actual no-flag result looks different from an unavailable or unmatched result.
5. Check that the whole-plan panel appears at two medicines, shows counts and Major/Moderate pairs, and its button opens the existing evidence-graded report. Print or export the report and confirm the diagnosis-to-medicines block appears at its header while pickers and whole-plan UI do not print.
6. Change a picker filter and add/remove medicines rapidly while screening is in flight. Confirm old badges disappear immediately and only the newest response appears. Remove a diagnosis after checking and confirm stale flags and the old report clear.
7. Temporarily make each new endpoint return 503 or disconnect the network. Confirm separate diagnosis-search, medicine-list, and live-screening errors with working Retry controls. Confirm no failure is shown as “no interaction found.” Restore the backend and retry.
8. Navigate entirely by keyboard through diagnosis selection, medicine checkboxes, details, the whole-plan check button, and diagnosis removal. Confirm focus stays in a useful control and the live regions announce searches and screening updates.
