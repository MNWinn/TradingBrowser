# 9-Agent Trading Research Architecture

A sophisticated hypothesis-driven system for rigorous strategy validation.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR AGENT                                     │
│                    (Orchestration & Control)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
┌───────────────┐          ┌──────────────────┐          ┌───────────────┐
│   MARKET      │          │     MIROFISH     │          │    RESEARCH   │
│  STRUCTURE    │          │     SIGNAL       │          │     AGENT     │
│    AGENT      │          │     AGENT        │          │               │
│               │          │                  │          │               │
│ • Price Action│          │ • Ingest Signals │          │ • Hypotheses  │
│ • Volatility  │          │ • Transform      │          │ • Backtests   │
│ • Trend       │          │ • Track Changes  │          │ • Optimization│
│ • Momentum    │          │ • Disagreement   │          │ • Walk-forward│
│ • Volume      │          │                  │          │               │
└───────┬───────┘          └────────┬─────────┘          └───────┬───────┘
        │                           │                            │
        └───────────────┬───────────┘                            │
                        │                                        │
                        ▼                                        │
              ┌──────────────────┐                               │
              │   STRATEGY AGENT │                               │
              │                  │                               │
              │ • Combine Signals│                               │
              │ • Formulate Ideas│                               │
              │ • Entry/Exit     │                               │
              │ • Risk/Reward    │◄──────────────────────────────┘
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │    RISK AGENT    │
              │                  │
              │ • Approve/Reject │
              │ • Position Sizing│
              │ • Exposure Limits│
              │ • Drawdown Ctrl  │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  EXECUTION SIM   │
              │     AGENT        │
              │                  │
              │ • Paper Trading  │
              │ • Slippage Model │
              │ • Fill Simulation│
              │ • PnL Tracking   │
              └────────┬─────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  EVALUATION  │ │  MEMORY  │ │   RESEARCH   │
│    AGENT     │ │ LEARNING │ │    AGENT     │
│              │ │   AGENT  │ │   (feedback) │
│ • Scorecards │ │          │ │              │
│ • Robustness │ │ • Lessons│ │ • New Hypo   │
│ • Graduation │ │ • Patterns│ │ • Refinement │
│ • Stability  │ │ • Priors │ │              │
└──────────────┘ └──────────┘ └──────────────┘
```

## Agent Descriptions

### 1. MarketStructureAgent (`market_structure_agent.py`)
**Purpose:** Analyze price action, volatility, trend, momentum, volume

**Key Functions:**
- Detect regime changes (trending, ranging, volatile)
- Classify market environments
- Calculate technical indicators (RSI, MACD, ATR, Bollinger Bands)
- Identify support/resistance levels
- Track pivot highs and lows

**Outputs:**
- Regime labels (TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE, etc.)
- Technical state (trend strength, volatility, momentum)
- Structure confidence score
- Support/resistance levels

### 2. MiroFishSignalAgent (`mirofish_signal_agent.py`)
**Purpose:** Ingest MiroFish predictive outputs and transform into structured signals

**Key Functions:**
- Parse MiroFish directional bias and confidence
- Track signal strength and confidence changes
- Detect internal disagreements in predictions
- Calculate model consensus
- Extract predictive features

**Outputs:**
- Directional bias (BULLISH, BEARISH, NEUTRAL, CONFLICTED)
- Confidence score (0.0 to 1.0)
- Predictive features
- Disagreement flags
- Model consensus score

### 3. ResearchAgent (`research_agent.py`)
**Purpose:** Test strategy hypotheses systematically

**Key Functions:**
- Propose new trading hypotheses
- Run parameter sweeps
- Test regime robustness
- Walk-forward optimization
- Monte Carlo simulation
- Identify failure modes

**Outputs:**
- Strategy variants with optimal parameters
- Performance summaries
- Failure mode analysis
- Robustness metrics

### 4. StrategyAgent (`strategy_agent.py`)
**Purpose:** Combine technical + predictive + contextual signals into trade ideas

**Key Functions:**
- Aggregate signals from multiple sources
- Calculate composite signal scores
- Formulate specific trade proposals
- Define entry, stop, target, exit logic
- Calculate conviction scores

**Outputs:**
- Trade proposals with full details
- Entry/exit rationale
- Risk/reward ratios
- Conviction scores and levels
- Setup quality grades (A, B, C)

### 5. RiskAgent (`risk_agent.py`)
**Purpose:** Reject poor trades and enforce risk limits

**Key Functions:**
- Assess trade risk
- Enforce position size limits
- Monitor portfolio exposure
- Prevent correlated entries
- Control drawdown

**Outputs:**
- Approve/Reject/Conditional decisions
- Risk-adjusted scores
- Violation lists
- Recommended position sizes

### 6. ExecutionSimulationAgent (`execution_simulation_agent.py`)
**Purpose:** Paper trade approved setups with realistic execution

**Key Functions:**
- Simulate order fills
- Model slippage based on volatility
- Track commissions
- Monitor trade lifecycle
- Record PnL

**Outputs:**
- Simulated fills with quality metrics
- Complete trade logs
- PnL tracking
- Execution quality metrics

### 7. EvaluationAgent (`evaluation_agent.py`)
**Purpose:** Study results across hundreds of trades

**Key Functions:**
- Calculate performance metrics (Sharpe, Sortino, Calmar)
- Analyze regime-specific performance
- Test statistical significance
- Check for overfitting
- Assess graduation readiness

**Outputs:**
- Scorecards with grades (A+ to F)
- Reliability analysis
- Stability metrics
- Graduation readiness assessment

### 8. MemoryLearningAgent (`memory_learning_agent.py`)
**Purpose:** Store lessons from wins/losses and update beliefs

**Key Functions:**
- Create lessons from trades
- Track setup performance
- Learn regime-specific patterns
- Update confidence frameworks
- Provide setup recommendations

**Outputs:**
- Pattern memory database
- Setup performance maps
- Updated Bayesian priors
- Lesson logs

### 9. SupervisorAgent (`supervisor_agent.py`)
**Purpose:** Orchestrate all sub-agents

**Key Functions:**
- Monitor agent health
- Assign tasks
- Resolve disagreements
- Escalate uncertainty
- Generate daily summaries
- Control system mode

**Outputs:**
- System state snapshots
- Research priorities
- Daily summaries
- Next action recommendations

## Message Bus Communication

All agents communicate via an asynchronous message bus with typed messages:

```python
class MessageType(Enum):
    # Market Data
    MARKET_STRUCTURE_UPDATE
    REGIME_CHANGE
    PRICE_ACTION_ALERT
    
    # MiroFish Signals
    MIROFISH_PREDICTION
    MIROFISH_SIGNAL_UPDATE
    
    # Research
    HYPOTHESIS_PROPOSED
    HYPOTHESIS_TESTED
    RESEARCH_RESULTS
    
    # Strategy
    TRADE_PROPOSAL
    STRATEGY_UPDATE
    SETUP_IDENTIFIED
    
    # Risk
    RISK_ASSESSMENT
    TRADE_APPROVED
    TRADE_REJECTED
    
    # Execution
    EXECUTION_FILL
    TRADE_OPENED
    TRADE_CLOSED
    PNL_UPDATE
    
    # Evaluation
    EVALUATION_COMPLETE
    SCORECARD_UPDATE
    
    # Memory/Learning
    LESSON_LEARNED
    PATTERN_DETECTED
    PRIOR_UPDATE
    
    # Supervisor
    TASK_ASSIGNMENT
    AGENT_STATUS
    SYSTEM_STATE
    DISAGREEMENT
    ESCALATION
```

## Usage

### Basic Usage

```python
import asyncio
from app.agents import TradingSystem

async def main():
    # Create and start system
    system = TradingSystem()
    await system.start()
    
    # Run simulation
    result = await system.run_simulation(
        tickers=["AAPL", "MSFT", "GOOGL"],
        num_days=30,
        trades_per_day=5
    )
    
    # Get evaluation
    report = await system.get_evaluation_report()
    print(f"Overall Grade: {report['scorecard']['overall_grade']}")
    
    await system.stop()

asyncio.run(main())
```

### Running Tests

```bash
# Run all tests
python -m pytest app/agents/test_9agent_architecture.py -v

# Run specific test class
python -m pytest app/agents/test_9agent_architecture.py::TestMarketStructureAgent -v

# Run large-scale simulation
python -m pytest app/agents/test_9agent_architecture.py::test_hundreds_of_trades -v
```

### Running Demo

```bash
python app/agents/demo.py
```

## Configuration

Each agent accepts configuration parameters:

```python
config = {
    "market_structure": {
        "lookback_periods": 100,
        "regime_threshold": 0.6,
    },
    "mirofish_signal": {
        "min_confidence": 0.5,
        "disagreement_threshold": 0.3,
    },
    "research": {
        "max_variants": 100,
        "min_trades": 30,
    },
    "strategy": {
        "min_conviction": 0.6,
        "min_risk_reward": 1.5,
    },
    "risk": {
        "max_position_size": 0.25,
        "max_drawdown": 0.10,
    },
    "execution_simulation": {
        "base_slippage": 0.0005,
        "commission": 1.0,
    },
    "evaluation": {
        "min_trades": 50,
        "min_graduation_trades": 100,
    },
    "memory_learning": {
        "min_observations": 3,
        "confidence_decay": 30,
    },
    "supervisor": {
        "heartbeat_interval": 30,
        "summary_interval": 24,
    },
}

system = TradingSystem(config)
```

## Hypothesis-Driven Workflow

The system is designed for rigorous hypothesis generation → testing → learning → conviction building:

1. **Hypothesis Generation** (ResearchAgent)
   - Propose new strategy ideas
   - Define entry/exit rules
   - Specify parameter ranges

2. **Signal Generation** (MarketStructureAgent + MiroFishSignalAgent)
   - Analyze market conditions
   - Generate predictive signals
   - Detect regime changes

3. **Trade Formulation** (StrategyAgent)
   - Combine multiple signals
   - Calculate conviction
   - Define risk/reward

4. **Risk Validation** (RiskAgent)
   - Check exposure limits
   - Validate risk/reward
   - Approve or reject

5. **Execution** (ExecutionSimulationAgent)
   - Paper trade approved setups
   - Model realistic fills
   - Track PnL

6. **Evaluation** (EvaluationAgent)
   - Calculate performance metrics
   - Test robustness
   - Check for overfitting

7. **Learning** (MemoryLearningAgent)
   - Store lessons
   - Track patterns
   - Update priors

8. **Orchestration** (SupervisorAgent)
   - Monitor all agents
   - Assign tasks
   - Generate reports

## Files

- `__init__.py` - Package initialization and exports
- `message_bus.py` - Inter-agent communication system
- `base_agent.py` - Base class for all agents
- `market_structure_agent.py` - Market analysis agent
- `mirofish_signal_agent.py` - MiroFish signal processing
- `research_agent.py` - Hypothesis testing
- `strategy_agent.py` - Trade formulation
- `risk_agent.py` - Risk management
- `execution_simulation_agent.py` - Paper trading
- `evaluation_agent.py` - Performance evaluation
- `memory_learning_agent.py` - Pattern learning
- `supervisor_agent.py` - System orchestration
- `trading_system.py` - Main system integration
- `test_9agent_architecture.py` - Comprehensive test suite
- `demo.py` - Demonstration script
- `README.md` - This file
