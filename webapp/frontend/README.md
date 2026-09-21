# PolyGuard Frontend

A fast, calm clinical decision-support frontend for medication interaction screening during consultations.

## Features
- **Doctor-focused clinical interface**: High-contrast, clean typography, zero ML jargon/internal confidence scores.
- **Debounced fuzzy medicine search**: 200ms debounce against `/api/drugs/search`.
- **Non-blocking unmatched fallback**: Explicit option to add unindexed drugs with clear limitation notices.
- **Color-coded severity banner**: Green (Minor/None), Amber (Moderate), Red (Major with clinical action prompt), Gray (Incomplete).
- **Collapsible pairwise interaction details**: Clean expandable table sorted worst-first.
- **Secondary multi-drug pattern signal**: Prompts pattern review only when elevated without fusing scores.
- **Configured for backend on `http://127.0.0.1:8765`**.

## Running Locally

1. **Start the backend** (if not already running):
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8765
   ```

2. **Start the frontend**:
   ```bash
   cd webapp/frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

## Running Tests & Production Build

- Run unit & integration tests:
  ```bash
  npm test
  ```
- Build production bundle:
  ```bash
  npm run build
  ```
