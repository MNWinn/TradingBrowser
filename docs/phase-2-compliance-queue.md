# Phase 2 Implementation: Compliance Violation Queue

Implemented on 2026-03-18.

## Backend

### New table
- `compliance_violations`
  - `id`
  - `policy_name`
  - `rule_code`
  - `severity` (`low|medium|high|critical`)
  - `status` (`open|acknowledged|waived|remediated`)
  - `symbol`
  - `details` (JSON)
  - `acknowledged_by`
  - `resolution_notes`
  - `resolved_at`
  - `created_at`, `updated_at`

Migration:
- `backend/alembic/versions/0004_compliance_violations.py`

### New API router
- `GET /compliance/violations?status=&limit=`
- `GET /compliance/summary`
- `POST /compliance/violations`
- `PATCH /compliance/violations/{violation_id}`

File:
- `backend/app/routers/compliance.py`

### Auto-capture from execution flow
`/execution/validate` and `/execution/order` now auto-record compliance violations when:
- live mode is disabled but order attempted
- adapter validation fails
- hard risk gate blocks order

File:
- `backend/app/routers/execution.py`

## Frontend

### API client support
Added:
- `getComplianceViolations()`
- `getComplianceSummary()`
- `updateComplianceViolation()`

File:
- `frontend/lib/api.ts`

### Dashboard panel
`Paper` section now includes a compliance queue panel with:
- summary counters (open/ack/waived/remediated)
- list of open violations
- acknowledge action per violation

File:
- `frontend/app/dashboard/page.tsx`

## Wire-up
- Router registered in:
  - `backend/app/main.py`
  - `backend/app/routers/__init__.py`
