# TradingBrowser

Production-style modular AI-assisted trading research and execution platform.

## Core Principles

- **Paper-first**: paper trading is default; live disabled by default
- **Observable decisions**: all signals/trades are explainable and logged
- **Execution abstraction**: same decision engine can route to research/paper/live/backtest
- **Hard server-side risk controls**: never bypassed
- **Adaptive learning**: soft constraints evolve only within hard ceilings

## Tech Stack

- Frontend: Next.js + TypeScript + Tailwind
- Backend: FastAPI + WebSocket
- Database: PostgreSQL
- Cache/PubSub: Redis
- Workers: Celery
- ML/Analytics: scikit-learn / XGBoost / optional PyTorch
- Broker: Alpaca (paper first)

## Monorepo Structure

- `frontend/` Next.js app (dashboard, workspace, strategy lab, paper/live consoles, etc.)
- `backend/` FastAPI services (signals, swarm orchestration, risk, execution adapters)
- `infra/db/schema.sql` canonical SQL schema
- `docs/` architecture, API contract, rollout & live-readiness

## Quick Start

### 1) Start infra + services

```bash
docker compose up --build
```

### 2) Backend local dev

> Docker Postgres is mapped to host port **5433** to avoid conflicts.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://trading:trading@localhost:5433/tradingbrowser
python3 -m alembic upgrade head
python3 -m scripts.seed_defaults
uvicorn app.main:app --reload --port 8000
```

Migration workflow:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Run minimal hardening tests:

```bash
cd backend
pytest -q
```

Testing guide:
- `docs/testing-playbook.md`

### 3) Frontend local dev

```bash
cd frontend
npm install
npm run dev
```

Open:
- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## Auth & Security (current phase)

Protected endpoints require a bearer token:

- `ADMIN_API_TOKEN` for policy/mode and credentials management
- `TRADER_API_TOKEN` for execution/fill operations
- `ANALYST_API_TOKEN` for read-only broker account/order views

Example:

```bash
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" http://localhost:8000/execution/mode
```

Broker credential encryption:
- credentials are encrypted at rest in `broker_accounts.encrypted_credentials`
- set `ENCRYPTION_KEY` before using `/settings/broker-accounts`

Webhook signature verification:
- `/alpaca/webhook/order-update` validates `x-alpaca-signature`
- set `ALPACA_WEBHOOK_SECRET`

## Modes & Safety

`MODE` runtime values:
- `research` -> recommendation only, no orders
- `paper` -> Alpaca paper order routing
- `live` -> live adapter only when explicitly enabled + strict gates pass

Additional mandatory controls:
- kill switch
- stale-data block
- confidence threshold block
- daily/weekly loss hard stops
- max position sizing/exposure guards
- auditable mode-change and execution logs

## MVP (v1)

- Real-time watchlist + market stream
- Chart workspace with probability drawer API
- Swarm orchestration with per-agent outputs
- Ensemble decision endpoint with consensus/disagreement
- Paper trading adapter through unified execution interface
- Risk engine hard guardrails
- Daily evaluation task scaffold

See `docs/` for full architecture, API contract, phased roadmap, and live-readiness checklist.
