# MiroFish Analytics Implementation

## Overview
Comprehensive analytics and visualization system for MiroFish predictions has been implemented.

## Files Created/Modified

### 1. Database Models
**File**: `backend/app/models/mirofish_predictions.py`

Three new database models:
- **MiroFishPrediction**: Stores every prediction with ticker, signal_type, confidence, timeframe, lens, metadata, price_at_prediction, timestamps
- **PredictionOutcome**: Tracks the outcome of predictions (actual_return, was_correct, outcome_price, outcome_time)
- **MiroFishAccuracySummary**: Pre-computed accuracy summaries for fast lookups

### 2. Analytics Service
**File**: `backend/app/services/mirofish/analytics.py`

Core analytics class `MiroFishAnalytics` with:

#### Data Classes
- `AccuracyMetrics`: Accuracy metrics with breakdowns by signal type, ticker, timeframe, and confidence calibration
- `PerformanceMetrics`: Trading performance metrics (win rate, Sharpe ratio, drawdown, profit factor)
- `TimeSeriesAnalysis`: Time series data (prediction trends, confidence evolution, signal strength, accuracy over time)
- `VisualizationData`: Data formatted for visualization (heatmaps, distributions, timelines)

#### Key Methods
- `store_prediction()`: Store new predictions
- `record_outcome()`: Record prediction outcomes
- `get_overall_accuracy()`: Get overall accuracy stats
- `get_ticker_accuracy()`: Per-ticker analysis
- `get_timeframe_accuracy()`: Per-timeframe analysis
- `get_time_series_analysis()`: Historical predictions timeline
- `get_performance_metrics()`: Trading performance metrics
- `get_signal_type_performance()`: Performance by LONG/SHORT/NEUTRAL
- `get_visualization_data()`: Data for charts and heatmaps

### 3. API Endpoints
**File**: `backend/app/routers/mirofish.py`

New endpoints added:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mirofish/analytics/accuracy` | GET | Overall accuracy stats with filters |
| `/mirofish/analytics/ticker/{ticker}` | GET | Per-ticker analysis |
| `/mirofish/analytics/timeframe/{timeframe}` | GET | Per-timeframe analysis |
| `/mirofish/analytics/timeline/{ticker}` | GET | Historical predictions timeline |
| `/mirofish/analytics/confidence` | GET | Confidence calibration analysis |
| `/mirofish/analytics/performance` | GET | Trading performance metrics |
| `/mirofish/analytics/signal-types` | GET | Performance by signal type |
| `/mirofish/analytics/visualization` | GET | Data for visualization |
| `/mirofish/analytics/store-prediction` | POST | Store a new prediction |
| `/mirofish/analytics/record-outcome` | POST | Record prediction outcome |

### 4. Model Exports
**File**: `backend/app/models/__init__.py`

Updated to export the new MiroFish prediction models.

### 5. Service Exports
**File**: `backend/app/services/mirofish/__init__.py`

Updated to export analytics classes and functions.

## Features Implemented

### 1. Prediction Tracking
- Store every MiroFish prediction with timestamp
- Track prediction outcomes (was it correct?)
- Calculate accuracy by ticker, timeframe, signal type
- Track confidence calibration (does high confidence = high accuracy?)

### 2. Time Series Analysis
- Prediction trend over time
- Confidence evolution
- Signal strength indicators
- Multi-timeframe alignment analysis

### 3. Performance Metrics
- Win rate by prediction type (LONG, SHORT, NEUTRAL)
- Average return per signal
- Sharpe ratio of MiroFish signals
- Drawdown analysis
- Best/worst performing tickers

### 4. Visualization Data
- Heat maps of prediction accuracy (ticker x timeframe)
- Confidence distribution charts
- Signal timeline data
- Correlation with actual price movements

## Usage Example

```python
# Store a prediction
from app.services.mirofish.analytics import store_prediction

prediction = store_prediction(
    ticker="AAPL",
    signal_type="LONG",
    confidence=0.85,
    timeframe="5m",
    price_at_prediction=150.0
)

# Later, record the outcome
from app.services.mirofish.analytics import record_outcome

record_outcome(
    prediction_id=prediction.id,
    actual_return=0.025,  # 2.5% return
    outcome_price=153.75,
    was_correct=True
)

# Get accuracy stats
from app.services.mirofish.analytics import get_overall_accuracy

metrics = get_overall_accuracy(days=30)
print(f"Accuracy: {metrics.accuracy_rate:.2%}")
```

## API Usage

```bash
# Get overall accuracy
curl "http://localhost:8000/mirofish/analytics/accuracy?days=30"

# Get per-ticker analysis
curl "http://localhost:8000/mirofish/analytics/ticker/AAPL?days=30"

# Get per-timeframe analysis
curl "http://localhost:8000/mirofish/analytics/timeframe/5m?days=30"

# Get timeline
curl "http://localhost:8000/mirofish/analytics/timeline/AAPL?days=30"

# Get confidence calibration
curl "http://localhost:8000/mirofish/analytics/confidence?days=30"

# Get performance metrics
curl "http://localhost:8000/mirofish/analytics/performance?days=30"

# Get visualization data
curl "http://localhost:8000/mirofish/analytics/visualization?days=30"

# Store prediction
curl -X POST "http://localhost:8000/mirofish/analytics/store-prediction" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "AAPL",
    "signal_type": "LONG",
    "confidence": 0.85,
    "timeframe": "5m",
    "price_at_prediction": 150.0
  }'

# Record outcome
curl -X POST "http://localhost:8000/mirofish/analytics/record-outcome" \
  -H "Content-Type: application/json" \
  -d '{
    "prediction_id": 1,
    "actual_return": 0.025,
    "outcome_price": 153.75
  }'
```

## Database Schema

The following tables are created:

1. **mirofish_predictions**: Stores predictions
2. **mirofish_prediction_outcomes**: Stores outcomes
3. **mirofish_accuracy_summaries**: Pre-computed summaries

Tables are automatically created on application startup via SQLAlchemy's `create_all()`.

## Dependencies

- numpy (for statistical calculations)
- sqlalchemy (for database operations)
- Existing TradingBrowser dependencies
