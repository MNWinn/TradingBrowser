# Phase 2.3: SLA + Traceability Enhancements

Date: 2026-03-18

## Added

### Backend analytics and operations
- New endpoint: `GET /compliance/analytics`
  - `mttr_hours`
  - `open_total`
  - `resolved_total`
  - `sla_overdue_open`
  - `severe_open`
  - `by_severity` counts
- Existing violation list now includes `age_seconds`.
- New bulk status endpoint: `PATCH /compliance/violations-bulk`.
- New export endpoint: `GET /compliance/violations/export.csv`.

Files:
- `backend/app/routers/compliance.py`
- `backend/app/schemas/compliance.py`

### Frontend compliance console
- Added KPI cards for MTTR/SLA/severity.
- Added SLA state visualization per row (ok / at-risk / breach).
- Added select-all + bulk actions.
- Added CSV export (authenticated fetch + download).
- Added journal deep link per violation (`/journal?symbol=...`).

Files:
- `frontend/app/compliance/page.tsx`
- `frontend/lib/api.ts`

### Journal deep-link handling
- Journal page now reads `?symbol=` from URL and applies client-side filter.

File:
- `frontend/app/journal/page.tsx`

## Validation
- `cd backend && pytest -q` ✅
- `cd frontend && npm run build` ✅
