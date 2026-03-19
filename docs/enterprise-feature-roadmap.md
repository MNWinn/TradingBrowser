# Enterprise Feature Roadmap (Market-Informed)

Date: 2026-03-18

## Research signals (public sources)

- **Palantir Foundry ontology docs** emphasize a semantic/operational layer linking data, models, actions, and security.
- **Bloomberg AIM product materials** emphasize end-to-end workflow: pre-trade, execution, compliance, post-trade, reconciliation, audit history.
- **BlackRock Aladdin Enterprise materials** emphasize a common data model, integrated risk analytics, and scalable operating model.
- **Regulatory guidance and best-practice articles** repeatedly stress: pre-trade controls, kill switches, model governance, and auditability.

## Recommended feature themes for TradingBrowser

### 1) Semantic trading ontology (Foundry-style)
- Add first-class entities: `Strategy`, `Signal`, `OrderIntent`, `Execution`, `RiskEvent`, `ModelVersion`, `Approval`.
- Explicit links:
  - `Signal -> ModelVersion`
  - `OrderIntent -> Signal`
  - `Execution -> OrderIntent`
  - `RiskEvent -> Execution`
- Why: gives enterprise-grade traceability and explainability across the full decision chain.

### 2) Enterprise compliance workflow (AIM-style)
- Add pre-trade rule packs (limit, concentration, restricted-list, max participation, notional caps).
- Add violation queue with disposition states: `open / acknowledged / waived / remediated`.
- Add post-trade compliance replay jobs and evidence export.

### 3) Risk cockpit + stress testing (Aladdin-style)
- Add scenario stress tests (gap risk, volatility spike, correlation breakdown).
- Add real-time risk budget depletion indicators and breach escalation policies.
- Add portfolio-level what-if engine before order submission.

### 4) Model governance + approval gates
- Register model versions, datasets, and feature lineage.
- Add mandatory approval checklist before promoting to paper/live.
- Add shadow mode and champion/challenger scoring dashboards.

### 5) Operational resilience + controls
- Circuit-breakers by symbol/strategy/venue.
- Immutable event log with replay tooling.
- Incident runbooks and one-click rollback for strategy config.

## Suggested implementation sequence

1. **Now (1–2 sprints):**
   - Add violation queue tables + API + dashboard panel.
   - Add model registry table + model version links in signal payload.
   - Add evidence export endpoint for audits.

2. **Near term (3–5 sprints):**
   - Add ontology-like linked entity graph for decision trace.
   - Add stress-test simulation service and pre-trade what-if checks.

3. **Mid term (6+ sprints):**
   - Add full approval workflow, SSO/RBAC, and per-desk tenancy.
   - Add SLA/incident management and runbook automation.

## KPIs to track

- % orders with complete decision lineage
- Compliance violation MTTR
- Manual override rate
- Model promotion lead time
- Risk breach frequency per 1,000 orders
