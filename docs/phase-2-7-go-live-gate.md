# Phase 2.7: Go-Live Gate + MiroFish Readiness

Date: 2026-03-18

Follow-on: [Phase 2.8: Readiness Trend History + Diagnostic One-Click](./phase-2-8-readiness-trend-history.md)

## Implemented

### Backend

#### New execution readiness endpoint
- `GET /execution/live-readiness`
- Role: admin/trader/analyst
- Returns:
  - `ready`
  - `checks` (`mirofish_live`, `compliance_overdue_zero`)
  - `reasons`
  - `compliance_overdue_open`
  - summarized MiroFish diagnostics

#### Live mode gating enforcement
- `PUT /execution/mode` now blocks live enable if readiness fails.
- Override supported with `force_enable_live=true`.
- Response now includes `live_readiness` snapshot when setting mode.

Schema update:
- `ModeUpdateRequest.force_enable_live: bool = False`

### MiroFish diagnostics enhancements
- `POST /mirofish/diagnostics` now includes:
  - `readiness_score`
  - `can_use_live`
  - `recommendations[]`
- Better `live_error` detail by endpoint.

### Frontend

#### Live Control page
- Added **Go Live Gate** panel with:
  - readiness status
  - MiroFish verdict/provider mode
  - compliance overdue count
  - reasons and recommendations
- Added `force enable live` override checkbox.

File:
- `frontend/app/live-control/page.tsx`

## Validation
- `cd backend && pytest -q` ✅
- `python3 scripts/functional_smoke.py` ✅
- `cd frontend && npm run build` ✅

## Verified behavior
- Live mode enable without readiness now returns 400 with explicit reasons.
- Live mode can still be set only via explicit force override.
- System reset back to paper mode after verification.
