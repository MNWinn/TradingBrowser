# Phase 2.9: Readiness Observability Pass

Date: 2026-03-19

## What shipped

### Backend
- Added `GET /execution/live-readiness/summary?limit=N`
  - Returns: `total`, `pass_count`, `fail_count`, `pass_rate`, `by_source`, `latest_at`
- Kept compatibility endpoint for trend consumers:
  - `GET /execution/readiness-history`
- Canonical trend endpoint remains:
  - `GET /execution/live-readiness/history`

### Frontend
- **Live Control** now shows:
  - snapshot count + short-window pass rate
  - trend-window rollup (`200` snapshots default)
- **Dashboard** readiness card now shows:
  - trend rollup (`pass/total`, percent)
  - still supports one-click run-all diagnostics

### Tests and smoke
- Backend test coverage extended to assert summary endpoint contract.
- Functional smoke extended to assert readiness summary response.

## Why this matters
Phase 2.7 introduced hard gating and Phase 2.8 introduced history.
Phase 2.9 adds operator-friendly **trend rollups** so teams can quickly see if the gate is consistently healthy or repeatedly failing.

## Current environment truth
Readiness still fails due to upstream MiroFish dependencies (missing `/predict` and chat bridge quota failure). Trend rollups make this persistent failure visible over time rather than as a one-off point check.
