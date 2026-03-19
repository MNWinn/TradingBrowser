# MiroFish Advanced Integration Layer

## Overview

The Advanced MiroFish Integration Layer extends the basic MiroFish service with sophisticated multi-timeframe analysis, intelligent caching, ensemble decision making, and paper trading capabilities.

## Architecture

```
backend/app/services/mirofish/
├── __init__.py              # Package exports
├── mirofish_fleet.py        # Multi-timeframe/multi-lens analysis
├── mirofish_cache.py        # Redis-based caching layer
├── mirofish_ensemble.py     # Ensemble decision making
└── mirofish_practice.py     # Paper trading practice mode
```

## Components

### 1. MiroFish Fleet (`mirofish_fleet.py`)

Manages multiple MiroFish assessments across timeframes and lenses.

**Features:**
- Multi-timeframe analysis (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
- Multiple lenses (technical, sentiment, fundamental, trend, momentum, volatility, catalyst, risk)
- Confidence aggregation (simple, weighted, threshold-based, timeframe-weighted)
- Disagreement detection between timeframes and lenses
- Focus ticker support with deeper analysis

**Key Classes:**
- `MiroFishFleet` - Main fleet manager
- `FleetAnalysis` - Complete analysis result
- `MiroFishAssessment` - Single assessment
- `ConfidenceAggregator` - Aggregation strategies
- `DisagreementDetector` - Conflict detection

**Usage:**
```python
from app.services.mirofish import get_fleet, fleet_analyze

# Quick analysis
result = await fleet_quick("AAPL")

# Deep analysis
fleet = get_fleet()
analysis = await fleet.deep_analysis("AAPL")

# Custom analysis
analysis = await fleet.analyze(
    ticker="AAPL",
    timeframes=["5m", "15m", "1h"],
    lenses=["technical", "sentiment"],
    aggregation_method="timeframe_weighted"
)
```

### 2. MiroFish Cache (`mirofish_cache.py`)

Redis-based caching layer with intelligent TTL management.

**Features:**
- Redis-based caching with local fallback
- Configurable TTL per ticker/timeframe
- Multiple invalidation strategies (TTL, market hours, volatility-based, event-driven)
- Automatic fallback to stale cache on fetch failure
- Cache warming and pre-fetching
- Statistics tracking

**Key Classes:**
- `MiroFishCache` - Main cache manager
- `CacheEntry` - Cached data container
- `CacheConfig` - Configuration options

**Usage:**
```python
from app.services.mirofish import get_cache, cached_assessment, invalidate_ticker_cache

# Get cached or fetch fresh
cache = get_cache()
result = await cache.get_or_fetch(
    ticker="AAPL",
    timeframe="5m",
    lens="technical",
    fetch_func=lambda: mirofish_predict({...})
)

# Convenience function
result = await cached_assessment("AAPL", "5m", "technical", fetch_func)

# Invalidate cache
await invalidate_ticker_cache("AAPL")

# Get stats
stats = await get_cache_stats()
```

### 3. MiroFish Ensemble (`mirofish_ensemble.py`)

Ensemble decision making integrating MiroFish with other agents.

**Features:**
- Weight MiroFish signals with other agents
- Historical accuracy tracking
- Dynamic weight adjustment based on performance
- Market regime adjustments (bull/bear/range)
- Volatility regime adjustments
- Conflict resolution between disagreeing signals

**Key Classes:**
- `MiroFishEnsemble` - Main ensemble manager
- `AgentSignal` - Signal from any source
- `HistoricalAccuracyTracker` - Performance tracking
- `DynamicWeightAdjuster` - Adaptive weighting
- `ConflictResolver` - Disagreement resolution

**Usage:**
```python
from app.services.mirofish import get_ensemble, ensemble_decision, create_agent_signal

# Ensemble decision
result = await ensemble_decision("AAPL", market_regime="bull")

# With custom signals
ensemble = get_ensemble()
agent_signals = [
    create_agent_signal("technical", "LONG", 0.7, "AAPL"),
    create_agent_signal("sentiment", "LONG", 0.6, "AAPL"),
]
result = await ensemble.ensemble_decision("AAPL", agent_signals=agent_signals)

# Record outcome for learning
ensemble.record_outcome(
    source=SignalSource.MIROFISH,
    ticker="AAPL",
    predicted_action=Action.LONG,
    actual_pnl=150.0
)
```

### 4. MiroFish Practice (`mirofish_practice.py`)

Paper trading practice mode for testing MiroFish configurations.

**Features:**
- Simulate trades based on MiroFish signals
- Track hypothetical P&L
- Compare different MiroFish configurations
- Pre-built configs: conservative, aggressive, balanced, swing
- Performance metrics (win rate, profit factor, Sharpe ratio, max drawdown)
- Learning from outcomes

**Key Classes:**
- `MiroFishPractice` - Main practice manager
- `PracticeSession` - Trading session
- `PracticeTrade` - Individual trade
- `MiroFishConfig` - Configuration

**Built-in Configurations:**
- `conservative` - High confidence, smaller positions, tighter stops
- `aggressive` - Lower thresholds, larger positions, wider stops
- `balanced` - Moderate settings (default)
- `swing` - Longer hold times, higher targets

**Usage:**
```python
from app.services.mirofish.mirofish_practice import (
    get_practice,
    create_practice_session,
    evaluate_trade_entry,
    simulate_trade,
    close_trade,
    get_session_results,
)

# Create session
session = await create_practice_session("Test Run", "balanced", 100000.0)

# Evaluate entry
decision = await evaluate_trade_entry(session["session_id"], "AAPL", 150.0)

# Enter trade
trade = await simulate_trade(
    session_id=session["session_id"],
    ticker="AAPL",
    direction="LONG",
    entry_price=150.0,
    quantity=100
)

# Exit trade
closed = await close_trade(
    session_id=session["session_id"],
    trade_id=trade["trade_id"],
    exit_price=155.0,
    exit_reason="target_hit"
)

# Get results
results = get_session_results(session["session_id"])
```

## API Endpoints

### Fleet Endpoints
- `POST /mirofish/fleet/analyze` - Comprehensive fleet analysis
- `POST /mirofish/fleet/quick` - Quick single-lens analysis
- `POST /mirofish/fleet/deep` - Deep analysis with all timeframes/lenses

### Cache Endpoints
- `POST /mirofish/cached/predict` - Cached prediction with fallback
- `POST /mirofish/cache/invalidate` - Invalidate cached entries
- `GET /mirofish/cache/stats` - Cache statistics

### Ensemble Endpoints
- `POST /mirofish/ensemble/decision` - Ensemble decision
- `GET /mirofish/ensemble/accuracy` - Accuracy report

### Practice Endpoints
- `POST /mirofish/practice/session/create` - Create practice session
- `GET /mirofish/practice/configs` - List configurations
- `POST /mirofish/practice/evaluate-entry` - Evaluate trade entry
- `POST /mirofish/practice/trade/enter` - Enter trade
- `POST /mirofish/practice/trade/exit` - Exit trade
- `POST /mirofish/practice/session/results` - Get session results
- `GET /mirofish/practice/sessions` - List sessions

## Integration with Existing Service

The advanced layer integrates seamlessly with the existing `mirofish.py` service:

```python
# In app/services/mirofish.py
from app.services.mirofish import (
    get_fleet,
    get_cache,
    get_ensemble,
    fleet_analyze,
    cached_assessment,
)

# New functions added:
# - mirofish_fleet_analysis()
# - mirofish_cached_predict()
# - mirofish_ensemble_decision()
# - mirofish_advanced_status()
```

## Configuration

The advanced layer uses existing configuration from `app.core.config.Settings`:

- `redis_url` - Redis connection for caching
- `mirofish_base_url` - MiroFish API endpoint
- `mirofish_api_key` - API authentication
- `mirofish_timeout_sec` - Request timeout
- `mirofish_focus_tickers` - Focus tickers for deeper analysis

## Performance Considerations

1. **Caching**: Reduces API calls to MiroFish backend
2. **Concurrency**: Fleet analysis uses semaphore-controlled concurrent requests
3. **TTL Management**: Shorter TTL for volatile tickers and intraday timeframes
4. **Fallback**: Graceful degradation to stale cache or stub responses

## Future Enhancements

- Machine learning for weight optimization
- Real-time market data integration for practice mode
- Backtesting framework integration
- Multi-ticker portfolio simulation
- Custom configuration builder UI
