# Phase 2.1: Compliance Console + Filtering

Date: 2026-03-18

## Added

### Backend filtering/sorting extensions
`GET /compliance/violations` now supports:
- `status`
- `severity`
- `symbol`
- `policy_name`
- `sort` (`newest`, `oldest`, `severity`)
- `limit`

File:
- `backend/app/routers/compliance.py`

### Frontend dedicated compliance page
New route:
- `/compliance`

Features:
- Summary counters (open/acknowledged/waived/remediated)
- Filters: status, severity, symbol
- Sorting: severity/newest/oldest
- Per-violation actions:
  - Acknowledge
  - Waive
  - Remediate
- Resolution notes input

File:
- `frontend/app/compliance/page.tsx`

### Navigation update
Added global nav entry to compliance page.

File:
- `frontend/components/AppShell.tsx`

### API client updates
`getComplianceViolations()` now accepts a structured filter object and sort mode.

File:
- `frontend/lib/api.ts`

## Validation
- `cd backend && pytest -q` ✅
- `cd frontend && npm run build` ✅
