Implemented the prescription-scanning improvements end-to-end.

Modified files:

- [prescription_scan.py](E:/Polypharmacy/webapp/prescription_scan.py)
  - Added conservative anti-guessing instructions.
  - Requested normalized 0–1000 bounding boxes.
  - Added defensive validation for object/array boxes; malformed boxes become `null`.
- [client.ts](E:/Polypharmacy/webapp/frontend/src/api/client.ts)
  - Added nullable `PrescriptionBoundingBox` typing.
- [PrescriptionScanReview.tsx](E:/Polypharmacy/webapp/frontend/src/components/PrescriptionScanReview.tsx)
  - Preserves the original client-side image via an object URL.
  - Renders per-medicine canvas crops when coordinates exist.
  - Revokes object URLs on replacement and unmount.
  - Added concise photo-quality guidance.
- [PrescriptionScanReview.test.tsx](E:/Polypharmacy/webapp/frontend/src/__tests__/PrescriptionScanReview.test.tsx)
  - Updated mock data for bounding boxes.
  - Added coverage for rows without bounding boxes.
  - Preserved the explicit doctor-confirmation safety gate.

No permanent files were created. `main.py` required no modification because the scan endpoint already passes the scanner response through unchanged.

Verification:

- TypeScript: zero errors.
- Frontend tests: all 22 tests passed across 7 files.
- Python AST checks: passed for `prescription_scan.py` and `main.py`.
- Defensive bounding-box validation checks: passed.
- `python -c "import main"`: loaded fully without traceback.
- `git diff --check`: no whitespace errors, only existing Windows line-ending warnings.
- Live Gemini test:
  - Used the real key directly from `webapp/.env` without displaying or moving it.
  - Generated an in-memory printed prescription containing Metformin, Amlodipine, and Atorvastatin.
  - The call succeeded and extracted all three medicines.
  - Gemini returned valid, usable normalized bounding boxes for all three rows.
  - The temporary test script was deleted afterward.

Known limitation: the successful live test used clear printed text. Bounding-box reliability for real handwritten prescriptions may be lower; missing or malformed boxes safely result in no crop while preserving the extracted review row.

No files were staged, committed, or pushed.