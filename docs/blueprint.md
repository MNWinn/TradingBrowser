# TradingBrowser Blueprint

## 1) Full Repo Structure

```text
TradingBrowser/
  backend/
    app/
      core/ (config, database)
      models/
      schemas/
      routers/
      services/ (market, chart analytics, signal, swarm, risk, execution)
      workers/ (celery)
      main.py
    requirements.txt
    Dockerfile
  frontend/
    app/ (dashboard, workspace, strategy lab, paper/live consoles, etc.)
    components/
    lib/
    package.json
    Dockerfile
  infra/db/schema.sql
  docs/blueprint.md
  docker-compose.yml
  README.md
```

## 2) Database Schema

Implemented in `infra/db/schema.sql` with all required domains:
- market data (`market_ticks`, `bars_*`)
- signals (`feature_snapshots`, `signal_outputs`, `mirofish_predictions`)
- swarm (`swarm_tasks`, `swarm_agent_runs`, `swarm_shared_memory`, `swarm_consensus_outputs`)
- execution (`execution_modes`, `paper_orders`, `live_orders`, fills)
- risk/capital (`risk_policies`, `capital_profiles`, `position_sizing_rules`, `stop_loss_profiles`)
- learning (`daily_model_evaluations`, `agent_performance_stats`, `model_versions`)
- governance (`trade_journal`, `audit_logs`)

## 3) Frontend Wireframe Plan

- **Left rail**: watchlist, signal freshness badges
- **Center**: chart workspace (candles + overlays + click interactions)
- **Right drawer**: probability stats, model confidence, recommendation explanation
- **Bottom console**: swarm logs, execution logs, worker queue health
- **Top status bar**: MODE + live warning banner + risk usage

Pages scaffolded:
- `/dashboard`
- `/workspace`
- `/strategy-lab`
- `/paper-console`
- `/live-control`
- `/training`
- `/journal`
- `/swarm`
- `/settings`

## 4) Backend Service Architecture

Logical services (modularized in `app/services`):
1. Market Data Service (REST + WS stream)
2. Chart Analytics Service (`/chart/probability`)
3. Probability Engine Service (scaffold)
4. MiroFish Adapter (`services/mirofish.py`)
5. Swarm Orchestrator (`services/swarm.py`)
6. Agent Worker Pool (async now, celery-ready next)
7. Ensemble Decision Engine (`services/signal_engine.py`)
8. Risk Engine (`services/risk.py`)
9. Execution Abstraction (`services/execution.py`)
10. Alpaca Paper Adapter (`AlpacaPaperAdapter`)
11. Live Adapter (`AlpacaLiveAdapter` gated)
12. Training/Evaluation (Celery task + endpoints)
13. Audit Service (endpoint + table)
14. Environment/Policy Control (`/execution/mode`, `/risk/policy`)

## 5) API Contract

Implemented routes:
- `/watchlist`
- `/market/quote/{ticker}`
- `/market/bars/{ticker}`
- `/chart/probability/{ticker}`
- `/signals/{ticker}`
- `/mirofish/predict`
- `/swarm/run/{ticker}`
- `/swarm/status/{task_id}`
- `/swarm/results/{ticker}`
- `/risk/profile`
- `/risk/policy`
- `/execution/mode` (GET/PUT)
- `/execution/validate`
- `/execution/order`
- `/execution/order/fill`
- `/alpaca/account`
- `/alpaca/orders`
- `/alpaca/webhook/order-update`
- `/settings/broker-accounts`
- `/settings/broker-accounts/{id}/credentials`
- `/training/run`
- `/evaluation/daily`
- `/strategies/backtest`
- `/audit/logs`
- `/journal`
- `/journal/{id}/outcome`
- `/swarm/performance`

## 6) Swarm Orchestration Design

Agents in parallel:
- market structure
- technical signal
- probability
- mirofish context
- news/catalyst
- risk
- execution eligibility
- learning

Orchestrator behavior:
- decomposes by agent role
- runs concurrently (`asyncio.gather` now; queue workers next)
- aggregates votes and computes consensus/disagreement
- keeps per-agent outputs traceable
- preserves conflict (disagreement score)

## 7) Signal Weighting Design

Current MVP signal combines:
- swarm aggregate vote
- consensus score boost
- disagreement penalty
- MiroFish included as first-class contextual vote and reason code

Next steps:
- agent reliability-weighted voting
- setup/regime-conditioned weights
- Bayesian / calibration layer

## 8) Modular Execution Layer Design

`ExecutionAdapter` interface:
- `validate_order`
- `estimate_position_size`
- `submit_order`
- `cancel_order`
- `monitor_order`
- `close_position`
- `get_account_state`

Adapters:
- `ResearchExecutionAdapter` (no orders)
- `AlpacaPaperAdapter`
- `AlpacaLiveAdapter` (hard-gated)

Factory switches by `MODE` with no decision-engine changes.

## 9) Adaptive Risk-Control Design

Hard rules (server-side, never bypass):
- kill switch
- max daily/weekly loss
- max concurrent positions
- max capital per trade
- mandatory stop-loss

Soft adaptive rules (bounded):
- confidence multipliers by regime
- position-size multipliers by setup
- stop/target profile tuning by observed outcomes

## 10) First MVP Implementation Plan

1. Land base monorepo + infra (done)
2. Replace in-memory watchlist with DB persistence (done in Phase 2)
3. Integrate Alpaca paper account/orders real endpoints (implemented with credential-aware adapter + mock fallback)
4. Hook chart clicks to `/chart/probability` (done in workspace scaffold)
5. Persist swarm runs + signal outputs + rationale (done in Phase 2)
6. Add daily evaluation pipeline and weight recalibration
7. Add auth + encrypted credential storage

## 11) Sample Code Scaffolding

Included in:
- Backend service scaffolds in `backend/app/services/*.py`
- API routers in `backend/app/routers/*.py`
- Next.js pages/components in `frontend/app` and `frontend/components`

## 11.1) Phase 2 Progress Snapshot

Completed in code:
- DB-backed watchlist/signals/swarm/audit persistence
- Runtime execution mode policy endpoint with explicit live confirmation token
- DB-backed hard/soft risk policy management
- Chart probability snapshot persistence (`feature_snapshots`)
- Trade journal creation from order submissions + outcome update endpoints
- Daily evaluation recalibration storing `daily_model_evaluations` and `agent_performance_stats`
- Alembic migration scaffolding + initial core migration
- Hardening pass: request schemas, idempotency table+keys, DB constraints/indexes, and baseline pytest coverage

## 12) Roadmap (v1 / v2 / v3)

- **v1 (paper-first)**: watchlist, chart workspace, swarm recommendations, paper execution, daily evaluation
- **v2 (adaptive intelligence)**: robust retraining loop, dynamic weights, richer strategy lab, agent reliability dashboards
- **v3 (controlled live)**: strict live readiness gate, approval policies, enhanced monitoring/alerts, multi-broker adapters

## 13) Paper -> Live Safety Recommendations

- Keep `MODE=paper` and `LIVE_TRADING_ENABLED=false` by default
- Require explicit live enable + policy approvals + audit record
- Enforce stricter live risk profile (smaller size, tighter drawdown caps)
- Require minimum paper sample size + expectancy + drawdown bounds
- Block trading on stale data, infra health degradation, or elevated disagreement
- Maintain one-click kill switch and alerting
- Roll out live in phased notional limits (shadow -> tiny size -> scaled)
