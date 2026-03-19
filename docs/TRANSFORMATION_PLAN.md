# TradingBrowser Transformation Plan
## AI Trading Research Platform - Comprehensive Assessment & Roadmap

**Date:** 2026-03-19  
**Repository:** MNWinn/TradingBrowser  
**Objective:** Transform existing codebase into production-style AI trading research platform

---

## Executive Summary

The TradingBrowser repository has a **strong foundation** with substantial infrastructure already in place. The transformation focuses on:
1. **Starting with SPY** as the single instrument for MVP
2. **Implementing real agent logic** (currently stubs)
3. **Building agent visibility dashboard** (missing)
4. **Completing the paper trading loop** with daily evaluation
5. **Enhancing MiroFish integration** with proper weighting

---

## A. CURRENT REPO UNDERSTANDING

### What Already Exists (Solid Foundation)

**Infrastructure & Architecture:**
- ✅ Monorepo structure with `frontend/`, `backend/`, `infra/db/`, `docs/`, `scripts/`
- ✅ Docker Compose setup for PostgreSQL, Redis, and services
- ✅ Alembic migrations with 6 migration files showing iterative development
- ✅ Comprehensive SQL schema covering all major domains
- ✅ FastAPI backend with 15+ routers already scaffolded
- ✅ Next.js frontend with 10+ pages and component library

**Backend Services (Implemented):**
- ✅ `execution.py` - Full ExecutionAdapter interface with Alpaca Paper/Live adapters
- ✅ `risk.py` - RiskEngine with hard/soft gate framework
- ✅ `swarm.py` - SwarmOrchestrator with 8 agent types
- ✅ `mirofish.py` - Sophisticated MiroFish integration with 3 fallback strategies
- ✅ `signal_engine.py` - EnsembleSignalEngine combining swarm outputs
- ✅ `market_data.py` - Alpaca data feed integration with WebSocket streaming
- ✅ `evaluation.py` - Daily recalibration of agent reliability scores
- ✅ `focus_runner.py` - Background deep swarm runner for focus tickers
- ✅ `compliance.py` - Violation queue with SLA tracking
- ✅ `audit.py` - Comprehensive audit logging

**Frontend (Implemented):**
- ✅ Dashboard with 7 sections
- ✅ Real-time WebSocket market stream hook
- ✅ Chart workspace with probability drawer
- ✅ Swarm console with per-agent visibility
- ✅ Paper trading console
- ✅ Compliance queue with violation management
- ✅ Live readiness diagnostics

### What's Scaffolded but Needs Refinement

| Component | Current State | Gap |
|-----------|---------------|-----|
| Market Structure Agent | Returns stub | Needs real trend analysis |
| Technical Signal Agent | Returns stub | Needs real indicators |
| Probability Agent | Returns stub | Needs ML probability model |
| News/Catalyst Agent | Returns stub | Needs news feed integration |
| Training Pipeline | Celery scaffold | Needs actual model training |
| Backtesting | Router exists | Needs implementation |
| Chart Indicators | Schema exists | Needs calculation service |

### Architecture Gaps Identified

1. **No Real-Time Agent Activity Dashboard** - Can't see what agents are doing right now
2. **No Agent Lifecycle Management** - Agents run once, no persistent state
3. **Limited Observability** - Basic logging, needs structured tracing
4. **No Market Regime Detection** - Schema has regime field but no detection logic
5. **Incomplete Learning Loop** - Evaluation exists but feedback is weak
6. **No Signal Persistence Layer** - Feature snapshots exist but feature engineering missing

---

## B. RECOMMENDED STRATEGY FOCUS: SPY

### Decision: Start with SPY (S&P 500 ETF)

| Factor | SPY | BTCUSD |
|--------|-----|--------|
| **Liquidity** | ✅ Highest ($20B+/day) | ✅ Excellent ($30B+) |
| **Volatility** | ✅ Moderate (VIX ~15-25) | ❌ High (10%+ swings) |
| **Signal Quality** | ✅ Rich data ecosystem | ⚠️ Emerging models |
| **Market Hours** | ✅ 9:30-16:00 ET only | ❌ 24/7 ops burden |
| **Paper Trading** | ✅ Alpaca excellent | ⚠️ Limited options |
| **MVP Simplicity** | ✅ Single ETF | ❌ Crypto complexity |
| **Research Depth** | ✅ Decades of research | ⚠️ Limited history |
| **Risk Controls** | ✅ Well-understood | ❌ Fat-tail events |

### Future Expansion Path

```
Phase 1: SPY only (prove the system)
Phase 2: Add QQQ, IWM (diversified indices)
Phase 3: Add sector ETFs (XLF, XLK, XLE)
Phase 4: Add individual large-caps (AAPL, MSFT, NVDA)
Phase 5: Consider BTC/ETH as separate asset class
```

---

## C. REFINED SYSTEM ARCHITECTURE

### Layer-by-Layer Design

#### 1. Dashboard / Frontend Layer
- **Agent Activity Stream**: Real-time view of all running agents
- **Drill-Down Agent View**: Click any agent to see logs, outputs, decisions
- **Probability Workspace**: Chart + signal overlay + explanation panel
- **Risk Cockpit**: Current exposure, limits usage, kill switch
- **Evaluation Dashboard**: Daily performance, agent reliability trends

#### 2. API / Backend Services Layer
- **Router Organization**: Add `/agents` router
- **WebSocket Endpoints**: `/ws/agents` for real-time status, `/ws/signals`

#### 3. Agent Orchestration Layer
- **Agent Registry**: Central registry of all agent types
- **Agent Lifecycle**: pending → running → completed → archived
- **Task Queue**: Celery for long-running, async for quick
- **Agent Communication**: Shared memory + message passing
- **Agent Health Monitoring**: Heartbeats, timeouts, restarts

#### 4. Market Data Ingestion Layer
- **Real-Time Feed**: Alpaca WebSocket → Redis PubSub
- **Historical Data**: Bars storage in PostgreSQL
- **Data Quality**: Stale detection, gap filling, validation
- **Feature Engineering**: Real-time indicator calculation

#### 5. Predictive Intelligence Layer
- **MiroFish Integration**: Existing 3-tier fallback
- **Technical Analysis**: RSI, MACD, Bollinger, VWAP, Volume Profile
- **Market Regime Detection**: Trending/mean-reverting/volatile classification
- **Ensemble Engine**: Weighted voting with confidence calibration
- **Signal Persistence**: Store all signals with full provenance

#### 6. Execution Layer
- **Adapter Pattern**: Existing ExecutionAdapter interface
- **Order Lifecycle**: intent → validation → submission → fill → journal
- **Paper Trading**: Alpaca paper with full fill simulation
- **Live Trading**: Gated behind strict controls
- **Idempotency**: Existing idempotency key system

#### 7. Risk Engine
- **Hard Gates** (never bypassed): Kill switch, max daily/weekly loss, max concurrent positions, max capital per trade, mandatory stop-loss, stale data block
- **Soft Adjustments** (adaptive): Position size by regime, confidence multipliers, setup-specific stop profiles

#### 8. Evaluation / Learning Layer
- **Daily Evaluation**: Existing recalibration
- **Agent Performance Tracking**: Per-agent, per-regime reliability
- **Strategy Performance**: Win rate, expectancy, drawdown tracking
- **Feedback Loop**: Poor performance → weight reduction → retraining

---

## D. AGENT SWARM DESIGN

### Agent Roles & Responsibilities

| Agent | Responsibility | Outputs |
|-------|---------------|---------|
| **Market Structure** | S/R levels, trend analysis | Key levels, trend direction |
| **Technical Analysis** | RSI, MACD, VWAP calculations | Indicator signals |
| **MiroFish Signal** | Predictive signals from MiroFish | Directional bias, confidence |
| **News/Catalyst** | News, earnings, events | Catalysts, risk events |
| **Market Regime** | Regime classification | Trending/mean-reverting/volatile |
| **Risk Assessment** | Pre-trade risk evaluation | Risk checks, position limits |
| **Execution Eligibility** | Signal → order decision | Eligibility, urgency |
| **Strategy/Ensemble** | Combine all signals | Final action, sizing |
| **Learning/Evaluation** | Post-trade analysis | Reliability updates |

### Agent Lifecycle

```
1. TASK CREATION → Orchestrator creates task, publishes to queue
2. AGENT DISPATCH → Spawn async tasks, set timeouts
3. AGENT EXECUTION → Read shared memory, analyze, write output
4. CONSENSUS BUILDING → StrategyAgent aggregates, calculates recommendation
5. DECISION PERSISTENCE → Save to DB, publish signal event
6. EXECUTION → Risk check, submit if approved
7. POST-TRADE → LearningAgent evaluates, updates scores
```

---

## E. DASHBOARD DESIGN

### Agent Activity Area

| Agent | Status | Task | Ticker | Last Output | Health |
|-------|--------|------|--------|-------------|--------|
| tech | RUNNING | Analyze SPY | SPY | 12s ago | 94% |
| miro | COMPLETE | Deep SPY | SPY | 45s ago | 91% |
| regime | PENDING | Detect Regime | SPY | -- | 78% |
| risk | COMPLETE | Check SPY | SPY | 8s ago | 100% |
| news | ERROR | Check News | SPY | 2m ago | 45% |

### Agent Drill-Down Sections
- **Agent Overview**: Status, health score, current task, runtime, uptime
- **Current Objective**: What the agent is working on
- **Progress Logs**: Real-time log stream
- **Recent Outputs**: Last 5 outputs with key metrics
- **Trade Ideas Produced**: Link to journal, statistics
- **Decisions Accepted/Rejected**: Acceptance rate, common reasons
- **Performance Contribution**: Win rate, returns, Sharpe ratio
- **Errors/Retries**: Error history, retry success rate

---

## F. MIROFISH INTEGRATION MODEL

### Signal Weighting

```python
class EnsembleWeights:
    def __init__(self):
        self.base_weights = {
            "mirofish_context": 0.35,
            "technical_signal": 0.30,
            "market_structure": 0.20,
            "news_catalyst": 0.15
        }
```

### Confidence Thresholds
- **paper_trade**: 0.65 minimum
- **live_trade**: 0.80 minimum
- **high_conviction**: 0.90 for increased sizing

### Conflict Handling
When MiroFish disagrees with majority:
1. Check historical accuracy in similar regimes
2. If MiroFish historically better → weight higher
3. If disagreement high → defer to WATCHLIST/NO_TRADE
4. Log conflict for learning

---

## G. PAPER TRADING AND EVALUATION LOOP

### Continuous Learning Loop

```
MARKET DATA → AGENTS ANALYZE → SIGNAL GENERATE → RISK CHECK
                                                  ↓
UPDATE WEIGHTS ← EVALUATE OUTCOME ← TRACK FILLS ← EXECUTE PAPER
```

### Daily Evaluation

```python
def run_daily_evaluation():
    for agent in agents:
        signals = get_signals_last_24h(agent)
        outcomes = get_outcomes_for_signals(signals)
        reliability = calculate_win_rate(outcomes)
        update_agent_reliability(agent, reliability)
    
    new_weights = calculate_optimal_weights(agents)
    update_ensemble_weights(new_weights)
```

---

## H. RISK CONTROLS

### Hard Constraints (Never Bypassed)

| Constraint | Default | Breach Behavior |
|------------|---------|-----------------|
| Kill Switch | False | Block all orders, manual reset |
| Max Daily Loss | $500 | Block new orders, allow closes |
| Max Weekly Loss | $1,500 | Block new orders, allow closes |
| Max Concurrent Positions | 5 | Block if limit reached |
| Max Capital Per Trade | $2,000 | Reject exceeding orders |
| Mandatory Stop Loss | Required | Reject without stop-loss |
| Stale Data Block | 60 seconds | Block if data > 60s old |
| Confidence Threshold | 0.65 | Block below threshold |

### Audit Requirements

All risk events logged with: timestamp, actor, event type, before/after state, reason

---

## I. PHASED IMPLEMENTATION ROADMAP

### Phase 0: Foundation Hardening (Weeks 1-2)
- Implement real Technical Analysis Agent (RSI, MACD, VWAP)
- Implement Market Regime Detection Agent
- Add comprehensive logging to all agents
- Create agent health monitoring endpoints

### Phase 1: Agent Orchestration (Weeks 3-4)
- Create AgentInstance and AgentLog database models
- Build AgentOrchestrator with lifecycle management
- Implement Redis-backed shared memory
- Create /agents API endpoints
- Build Agent Activity dashboard component
- Implement WebSocket agent status stream

### Phase 2: Market Data Pipeline (Weeks 5-6)
- Implement Alpaca WebSocket consumer
- Build Redis PubSub for market data distribution
- Create feature engineering service
- Add data quality monitoring
- Build market regime detection

### Phase 3: MiroFish Enhancement (Weeks 7-8)
- Implement MiroFish signal caching layer
- Build confidence calibration system
- Implement dynamic ensemble weighting
- Create conflict detection and resolution
- Enhance MiroFish health monitoring

### Phase 4: Paper Trading Loop (Weeks 9-10)
- Implement order lifecycle tracking
- Create trade journal auto-population
- Implement outcome tracking
- Build daily evaluation pipeline
- Create evaluation dashboard

### Phase 5: Observability & Polish (Weeks 11-12)
- Implement structured logging (JSON)
- Add correlation IDs across request chain
- Build metrics collection
- Create alerting rules
- Performance optimization

### Phase 6: Live Readiness (Weeks 13-14)
- Harden live trading gates
- Implement additional safety checks
- Create live trading runbook
- Add compliance workflow enhancements
- Stress test the system

---

## J. CONCRETE NEXT CODING STEPS

### Immediate Priority (This Week)

#### 1. Create Directory Structure
```bash
mkdir -p backend/app/services/agents
mkdir -p backend/app/services/indicators
mkdir -p frontend/app/components/agents
```

#### 2. Technical Analysis Agent
**File:** `backend/app/services/agents/technical_analysis.py`
- Implement RSI, MACD, VWAP, Bollinger Bands calculations
- Connect to market data service
- Return structured output with indicator values and signals

#### 3. Market Regime Detection Agent
**File:** `backend/app/services/agents/regime_detection.py`
- Calculate realized volatility
- Calculate ADX for trend strength
- Classify into regimes: trending_up/down, mean_reverting, volatile, calm

#### 4. Database Migration
**File:** `backend/alembic/versions/0007_agent_instances.py`
- Create `agent_instances` table
- Create `agent_logs` table
- Add indexes for performance

#### 5. Agents Router
**File:** `backend/app/routers/agents.py`
- GET /agents - List all agents
- GET /agents/{id} - Get agent details
- GET /agents/{id}/logs - Get agent logs
- GET /agents/{id}/outputs - Get agent outputs
- WS /agents/ws - WebSocket for real-time updates

#### 6. Agent Orchestrator Service
**File:** `backend/app/services/agents/orchestrator.py`
- Manage agent lifecycle
- Handle task queue
- Coordinate agent communication
- Track agent health

#### 7. Frontend Agent Components
**Files:**
- `frontend/components/agents/AgentActivityTable.tsx`
- `frontend/components/agents/AgentDetailPanel.tsx`
- `frontend/components/agents/AgentHealthBadge.tsx`

#### 8. Update Swarm Service
**File:** `backend/app/services/swarm.py`
- Replace stub agents with real implementations
- Integrate with AgentOrchestrator
- Add proper logging and error handling

#### 9. API Integration
**File:** `frontend/lib/api.ts`
- Add agent-related API functions
- Add WebSocket connection for agent updates

#### 10. Dashboard Updates
**File:** `frontend/app/dashboard/page.tsx` or new `frontend/app/agents/page.tsx`
- Add Agent Activity section
- Link to agent detail views

---

## Summary

The TradingBrowser repository is **well-architected** with strong foundations. The transformation to a production-style AI trading platform requires:

1. **Focusing on SPY** for the MVP to prove the system
2. **Implementing real agent logic** to replace stubs
3. **Building agent visibility** through the dashboard
4. **Completing the paper trading loop** with daily evaluation
5. **Enhancing MiroFish integration** with proper signal processing

The phased roadmap provides a practical 14-week path from the current state to a fully operational research platform.
