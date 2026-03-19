# Phase 2.2: Compliance Ops Enhancements

Date: 2026-03-18

## Implemented

### Backend
- Added **bulk disposition endpoint**:
  - `PATCH /compliance/violations-bulk`
  - payload: `ids[]`, `status`, `acknowledged_by?`, `resolution_notes?`
- Added **CSV export endpoint**:
  - `GET /compliance/violations/export.csv`
  - supports filters: `status`, `severity`, `symbol`, `policy_name`, `sort`
- Added `age_seconds` field in serialized violation responses.

Files:
- `backend/app/routers/compliance.py`
- `backend/app/schemas/compliance.py`

### Frontend
- Compliance page now supports:
  - row selection + select-all
  - bulk actions: acknowledge / waive / remediate
  - aging labels (e.g., `3h`, `2d`)
  - CSV export button
- API client updates:
  - `bulkUpdateComplianceViolations()`
  - `exportComplianceCsv()`

Files:
- `frontend/app/compliance/page.tsx`
- `frontend/lib/api.ts`

## Validation
- `cd backend && pytest -q` ✅
- `cd frontend && npm run build` ✅
