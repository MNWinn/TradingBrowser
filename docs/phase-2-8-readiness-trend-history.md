# Phase 2.8: Readiness Trend History + Diagnostic One-Click

Date: 2026-03-19

## Summary
Phase 2.8 extends the go-live safety gate by making readiness observable over time and easier to refresh from the UI.

This phase adds:
- readiness trend persistence and history retrieval
- explicit endpoint contracts for trend reads
- a one-click Live Control diagnostics action
- smoke coverage for trend/history behavior
- regression guarantees for existing phase 2.7 live-gate behavior

See also: [Phase 2.7: Go-Live Gate + MiroFish Readiness](./phase-2-7-go-live-gate.md).

## Backend contract updates

### 1) Readiness snapshots persisted
A readiness snapshot is now recorded when:
- `GET /execution/live-readiness` is evaluated
- a live-enable attempt is made via `PUT /execution/mode` (including blocked attempts)

Each snapshot stores at least:
- timestamp
- overall readiness (`ready`)
- key checks (MiroFish/compliance)
- reasons
- MiroFish summary (verdict/score/recommendations when available)
- context (source path such as periodic refresh vs mode-change attempt)

### 2) Trend/history endpoint(s)
New execution API surface provides trend retrieval for UI and smoke assertions.

Expected response shape includes:
- latest snapshot
- ordered history list (newest-first)
- bounded query controls (for example: `limit`)

Implementation note: these are read-only diagnostics endpoints and must not alter mode state.

## Frontend behavior updates

### Live Control: one-click diagnostics action
Live Control now includes a direct action to run/refresh all diagnostics used by the go-live gate (instead of only a readiness fetch).

UX goals:
- one click from operator workflow
- clear latest status and trend visibility
- no hidden mode toggle side effects

## Smoke test additions
Functional smoke now verifies Phase 2.8 pathing in addition to existing phase 2.7 checks:
- readiness evaluation still returns valid gate payload
- trend/history endpoint returns latest + history list contract
- ordering/limit behavior is stable enough for operator UI usage
- live-mode gate semantics remain enforced

## Regression guarantees
Phase 2.8 must preserve:
- phase 2.7 live enable block when readiness fails
- `force_enable_live=true` explicit override behavior
- readiness reason transparency in API responses
- existing MiroFish diagnostics endpoint behavior

In short: trend/history and one-click diagnostics are additive observability/UX improvements, not policy relaxations.

## Test/readiness framing
This phase aligns with the testing playbook emphasis on repeatable safety verification before go-live and on preventing regressions in critical controls.

Reference: `docs/testing-playbook.md` (go-live readiness/testing guidance).
