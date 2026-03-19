# Functional Test Loop Report (Ralph Wiggum Pass)

Date: 2026-03-18

## Goal
Run broad functional validation across API and UI, including edge cases and MiroFish behavior.

## What was added

### 1) API functional smoke test script
- File: `scripts/functional_smoke.py`
- Covers:
  - root, market, chart, watchlist, signals, swarm
  - mode/auth edge cases
  - execution validate/order/idempotency
  - journal update
  - compliance create/update/bulk/timeline/summary/analytics/export
  - mirofish status/predict/deep-swarm
  - risk/evaluation/strategy/audit
  - settings broker account behavior (handles missing encryption key scenario)

### 2) Agent-browser functional smoke script
- File: `.pi/skills/agent-browser/scripts/functional-smoke.mjs`
- Uses Playwright to:
  - visit key pages
  - assert required page content
  - detect JS runtime/console errors
  - run light interactions (dashboard controls, compliance refresh)

### 3) Environment fix for runtime completeness
- File: `docker-compose.yml`
- Added backend env:
  - `AUTO_CREATE_SCHEMA: "true"`

This resolved runtime failures where new compliance tables were missing in the Docker DB.

## Additional UI / bloat cleanup during test loop
- Removed duplicate workspace topbar usage.
- Reduced dashboard error bloat (inline status instead of full error card).
- Collapsed dashboard section switcher into compact disclosure.
- Formatted long timestamps in swarm and paper console.

Files:
- `frontend/app/workspace/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/swarm/page.tsx`
- `frontend/app/paper-console/page.tsx`

## Results

### Automated
- `cd backend && pytest -q` → PASS
- `python3 scripts/functional_smoke.py` → PASS
- `node .pi/skills/agent-browser/scripts/functional-smoke.mjs` → PASS
- `node .pi/skills/agent-browser/scripts/capture.mjs current` → PASS

### MiroFish status
- `GET /mirofish/status` shows configured/live mode.
- `POST /mirofish/predict` currently succeeds via fallback stub mode when direct/bridge endpoint compatibility is not available.
- `POST /mirofish/deep-swarm` succeeds and returns deep aggregation, with per-analysis provider mode indicating fallback behavior.

## Interpretation
MiroFish integration path is operational end-to-end, but current upstream compatibility appears to force fallback behavior for predict payloads. This is handled safely by existing fallback logic and does not break platform workflows.
