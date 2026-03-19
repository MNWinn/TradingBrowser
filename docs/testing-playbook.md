# TradingBrowser Testing Playbook

This project is at the stage where **testing depth is more important than adding major new auth architecture**.

## Why we are focusing on testing now

JWT + DB-backed RBAC + immutable audit chain are valuable, but not blocking for immediate paper-mode validation. Before adding those, you should validate:

1. risk gates are never bypassed
2. mode switching behaves safely
3. idempotency prevents duplicate orders/fill updates
4. journal and audit integrity are consistent
5. webhook signature checks work under normal and hostile cases

---

## Test Pyramid for this repo

## 1) Unit tests (fast, every commit)

Current suite already includes:
- mode transition checks
- risk gate checks
- schema validation checks
- encryption/signature helper checks

Run:

```bash
cd backend
pytest -q
```

Target runtime: < 10s.

## 2) API integration tests (next priority)

Add tests for:
- `/execution/mode` role enforcement and live confirmation token
- `/execution/order` with/without idempotency key
- `/execution/order/fill` idempotent replay behavior
- `/alpaca/webhook/order-update` valid/invalid signature behavior
- `/risk/policy` admin-only updates

Suggested approach:
- use `TestClient`
- use dedicated test database URL
- reset DB per test session

## 3) End-to-end smoke (manual or scripted)

Core smoke path:
1. set mode to `paper`
2. generate signal
3. submit order
4. post fill update
5. verify journal updated
6. run `/evaluation/daily`

---

## Required test environments

## Local fast lane
- run unit tests only
- run static checks and compile checks

## Local integration lane
- start Postgres + Redis via docker compose
- run migration + seed
- run API integration tests

## Staging lane
- realistic environment variables
- webhook signing enabled
- mock alpaca credentials or paper account

---

## Concrete weekly testing workflow

## Daily (developer loop)

```bash
cd backend
python3 -m compileall app tests scripts
pytest -q
```

## Before merging feature branches

```bash
docker compose up -d postgres redis
cd backend
alembic upgrade head
python -m scripts.seed_defaults
pytest -q
```

Then run manual smoke checklist below.

---

## Manual smoke checklist (paper-mode safety)

1. `PUT /execution/mode` to paper with admin token
2. `POST /execution/order` without stop-loss -> blocked
3. `POST /execution/order` valid payload -> accepted, journal_id returned
4. Repeat same payload with same idempotency key -> `idempotent_replay=true`
5. `POST /execution/order/fill` with idempotency key
6. Repeat fill update same key -> replay response
7. `GET /journal` confirms outcome state transitions
8. `POST /evaluation/daily` stores reliability metrics
9. `POST /alpaca/webhook/order-update` with bad signature -> 401
10. same endpoint with valid signature -> update accepted

---

## Priority backlog for testing (recommended order)

1. Add API integration tests for execution/risk/auth routes
2. Add regression tests around idempotency table behavior
3. Add load test for websocket and order endpoints (k6 or Locust)
4. Add fault-injection tests (stale data, redis unavailable, alpaca API timeout)
5. Add CI workflow gates:
   - compile check
   - pytest unit+integration
   - migration up/down validation

---

## Notes on future security improvements

JWT + persistent RBAC are still recommended for v2 live-readiness.
They are not the immediate bottleneck right now; repeatable testing and safety verification is.
