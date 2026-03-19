# Phase 2.4: Compliance Timeline, Ownership, and SLA Alerts

Date: 2026-03-18

## Backend changes

### Ownership
- Added `assignee` field to compliance violations.
- Migration: `backend/alembic/versions/0005_compliance_assignee.py`

### Timeline API
- Added endpoint:
  - `GET /compliance/violations/{violation_id}/timeline?limit=100`
- Timeline includes create/update/bulk-update audit events tied to the violation.

### Existing endpoints enhanced
- `GET /compliance/violations` now includes `assignee`.
- `PATCH /compliance/violations/{id}` supports `assignee` updates.
- `PATCH /compliance/violations-bulk` supports optional `assignee`.
- CSV export now includes `assignee` column.

Files:
- `backend/app/models/entities.py`
- `backend/app/schemas/compliance.py`
- `backend/app/routers/compliance.py`

## Frontend changes

### Compliance console (`/compliance`)
- Per-violation owner input + "Save Owner" action.
- Timeline toggle per violation (Show/Hide Timeline).
- Timeline entries rendered inline.
- Row metadata now shows owner.

### Dashboard alerts
- Dashboard status strip now displays compliance open + overdue counts.
- Added SLA overdue alert banner when overdue count > 0.

### API client additions
- `getComplianceViolationTimeline()`
- Existing update/bulk update payloads now accept `assignee`.

Files:
- `frontend/app/compliance/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/lib/api.ts`

## Validation
- `cd backend && pytest -q` ✅
- `cd frontend && npm run build` ✅

## Required step
Run migrations:

```bash
cd backend
alembic upgrade head
```
