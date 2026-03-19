from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.services.mirofish_service import (
    mirofish_deep_swarm,
    mirofish_diagnostics,
    mirofish_predict,
    mirofish_status,
    mirofish_fleet_analysis,
    mirofish_cached_predict,
    mirofish_ensemble_decision,
    mirofish_advanced_status,
)
from app.services.mirofish.mirofish_practice import (
    get_practice,
    create_practice_session,
    evaluate_trade_entry,
    simulate_trade,
    close_trade,
    get_session_results,
    get_available_configs,
    TradeDirection,
    ExitReason,
)

router = APIRouter(prefix="/mirofish", tags=["mirofish"])


@router.get("/status")
def status():
    return mirofish_status()


@router.post("/predict")
async def predict(payload: dict):
    return await mirofish_predict(payload)


@router.post("/deep-swarm")
async def deep_swarm(payload: dict):
    return await mirofish_deep_swarm(payload)


@router.post("/diagnostics")
async def diagnostics(payload: dict | None = None):
    return await mirofish_diagnostics(payload or {})


# Advanced Layer Endpoints

@router.get("/advanced/status")
async def advanced_status():
    """Get status of the advanced MiroFish integration layer."""
    return await mirofish_advanced_status()


@router.post("/fleet/analyze")
async def fleet_analyze(payload: dict):
    """
    Run comprehensive fleet analysis with multi-timeframe, multi-lens assessment.
    
    Request body:
    - ticker: str (required)
    - timeframes: list[str] (optional, defaults based on focus status)
    - lenses: list[str] (optional, defaults based on focus status)
    - aggregation_method: str (optional, default: "weighted")
    """
    ticker = payload.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    
    return await mirofish_fleet_analysis(
        ticker=ticker,
        timeframes=payload.get("timeframes"),
        lenses=payload.get("lenses"),
        aggregation_method=payload.get("aggregation_method", "weighted"),
    )


@router.post("/fleet/quick")
async def fleet_quick(payload: dict):
    """
    Quick fleet analysis with single lens across timeframes.
    
    Request body:
    - ticker: str (required)
    - timeframes: list[str] (optional, default: ["5m", "15m", "1h"])
    """
    from app.services.mirofish import fleet_quick
    
    ticker = payload.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    
    return await fleet_quick(
        ticker=ticker,
        timeframes=payload.get("timeframes"),
    )


@router.post("/fleet/deep")
async def fleet_deep(payload: dict):
    """
    Deep fleet analysis with all timeframes and lenses.
    Best for focus tickers requiring comprehensive evaluation.
    
    Request body:
    - ticker: str (required)
    """
    from app.services.mirofish import fleet_deep
    
    ticker = payload.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    
    return await fleet_deep(ticker=ticker)


@router.post("/cached/predict")
async def cached_predict(payload: dict):
    """
    Get cached MiroFish prediction with automatic fallback.
    
    Request body:
    - ticker: str (required)
    - timeframe: str (optional, default: "5m")
    - lens: str (optional, default: "overall")
    - force_refresh: bool (optional, default: false)
    """
    ticker = payload.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    
    return await mirofish_cached_predict(
        ticker=ticker,
        timeframe=payload.get("timeframe", "5m"),
        lens=payload.get("lens", "overall"),
        force_refresh=payload.get("force_refresh", False),
    )


@router.post("/cache/invalidate")
async def cache_invalidate(payload: dict):
    """
    Invalidate cached entries.
    
    Request body:
    - ticker: str (optional) - invalidate all entries for ticker
    - timeframe: str (optional) - invalidate specific timeframe
    - lens: str (optional) - invalidate specific lens
    """
    from app.services.mirofish import invalidate_ticker_cache
    
    ticker = payload.get("ticker")
    
    if ticker:
        count = await invalidate_ticker_cache(ticker)
        return {"invalidated": count, "ticker": ticker}
    
    # If no ticker, invalidate all (be careful!)
    cache = get_cache()
    count = await cache.clear_all()
    return {"invalidated": count, "scope": "all"}


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    from app.services.mirofish import get_cache_stats
    return await get_cache_stats()


@router.post("/ensemble/decision")
async def ensemble_decision(payload: dict):
    """
    Generate ensemble decision combining MiroFish with other signals.
    
    Request body:
    - ticker: str (required)
    - include_deep_analysis: bool (optional, default: true)
    - market_regime: str (optional) - "bull", "bear", or "range"
    """
    ticker = payload.get("ticker")
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    
    return await mirofish_ensemble_decision(
        ticker=ticker,
        include_deep_analysis=payload.get("include_deep_analysis", True),
        market_regime=payload.get("market_regime"),
    )


@router.get("/ensemble/accuracy")
async def ensemble_accuracy():
    """Get ensemble accuracy tracking report."""
    from app.services.mirofish import get_ensemble
    ensemble = get_ensemble()
    return ensemble.get_accuracy_report()


# Deep Dive Endpoints

@router.get("/explain/{prediction_id}")
async def explain_prediction(prediction_id: str):
    """
    Explain a MiroFish prediction by breaking down its components.
    
    Returns:
    - Factor weights and contributions
    - Key drivers identification
    - Confidence breakdown by component
    - Contradicting signals detection
    """
    from app.services.mirofish import get_explanation
    
    explanation = await get_explanation(prediction_id)
    if not explanation:
        raise HTTPException(status_code=404, detail=f"Explanation not found for prediction_id: {prediction_id}")
    
    return explanation


@router.post("/explain/generate")
async def generate_explanation(payload: dict):
    """
    Generate a new explanation for a prediction.
    
    Request body:
    - prediction_id: str (required)
    - ticker: str (required)
    - prediction: dict (required) - raw prediction data
    - timeframe: str (optional, default: "5m")
    - lens: str (optional, default: "overall")
    - market_regime: str (optional) - "bull", "bear", or "range"
    """
    from app.services.mirofish import explain_prediction
    
    prediction_id = payload.get("prediction_id")
    ticker = payload.get("ticker")
    prediction = payload.get("prediction")
    
    if not all([prediction_id, ticker, prediction]):
        raise HTTPException(status_code=400, detail="prediction_id, ticker, and prediction are required")
    
    return await explain_prediction(
        prediction_id=prediction_id,
        ticker=ticker,
        raw_prediction=prediction,
        timeframe=payload.get("timeframe", "5m"),
        lens=payload.get("lens", "overall"),
        market_regime=payload.get("market_regime"),
    )


@router.get("/scenarios/{ticker}")
async def get_scenarios(ticker: str, current_price: float | None = None, timeframe: str = "5m"):
    """
    Get scenario analysis for a ticker.
    
    Path parameters:
    - ticker: str (required)
    
    Query parameters:
    - current_price: float (optional) - current market price
    - timeframe: str (optional, default: "5m")
    
    Returns:
    - What-if scenarios for different price movements
    - Best case / worst case scenarios
    - Probability distribution of outcomes
    - Risk/reward analysis
    """
    from app.services.mirofish import analyze_scenarios
    
    if not current_price:
        # Try to get current price from prediction
        prediction = await mirofish_predict({"ticker": ticker, "timeframe": timeframe})
        current_price = prediction.get("metadata", {}).get("current_price", 100.0)
    
    return await analyze_scenarios(
        ticker=ticker,
        current_price=current_price,
        timeframe=timeframe,
    )


@router.post("/scenarios/monte-carlo")
async def monte_carlo_simulation(payload: dict):
    """
    Run Monte Carlo simulation for price scenarios.
    
    Request body:
    - ticker: str (required)
    - current_price: float (required)
    - num_simulations: int (optional, default: 1000)
    - timeframe: str (optional, default: "5m")
    """
    from app.services.mirofish import run_monte_carlo
    
    ticker = payload.get("ticker")
    current_price = payload.get("current_price")
    
    if not all([ticker, current_price]):
        raise HTTPException(status_code=400, detail="ticker and current_price are required")
    
    return await run_monte_carlo(
        ticker=ticker,
        current_price=float(current_price),
        num_simulations=payload.get("num_simulations", 1000),
        timeframe=payload.get("timeframe", "5m"),
    )


@router.post("/backtest")
async def run_backtest(payload: dict):
    """
    Run backtest on historical data.
    
    Request body:
    - ticker: str (required)
    - historical_data: list[dict] (required) - list of price bars with date and close
    - config: dict (optional) - backtest configuration
    - name: str (optional) - backtest name
    
    Configuration options:
    - entry_threshold: float (default: 0.6) - min confidence to enter
    - stop_loss_pct: float (default: 0.05) - stop loss percentage
    - take_profit_pct: float (default: 0.10) - take profit percentage
    - max_position_size: float (default: 0.2) - max % of capital per trade
    - max_holding_days: int (default: 5)
    - use_deep_swarm: bool (default: false)
    """
    from app.services.mirofish import run_backtest as backtest_run
    
    ticker = payload.get("ticker")
    historical_data = payload.get("historical_data")
    
    if not all([ticker, historical_data]):
        raise HTTPException(status_code=400, detail="ticker and historical_data are required")
    
    return await backtest_run(
        ticker=ticker,
        historical_data=historical_data,
        config=payload.get("config"),
        name=payload.get("name"),
    )


@router.post("/backtest/optimize")
async def optimize_backtest(payload: dict):
    """
    Optimize backtest parameters using grid search.
    
    Request body:
    - ticker: str (required)
    - historical_data: list[dict] (required)
    - param_grid: dict (optional) - parameter ranges to test
    
    Example param_grid:
    {
        "entry_threshold": [0.5, 0.6, 0.7],
        "stop_loss_pct": [0.03, 0.05, 0.07],
        "take_profit_pct": [0.08, 0.10, 0.15]
    }
    """
    from app.services.mirofish import optimize_parameters
    
    ticker = payload.get("ticker")
    historical_data = payload.get("historical_data")
    
    if not all([ticker, historical_data]):
        raise HTTPException(status_code=400, detail="ticker and historical_data are required")
    
    return await optimize_parameters(
        ticker=ticker,
        historical_data=historical_data,
        param_grid=payload.get("param_grid"),
    )


@router.post("/backtest/walk-forward")
async def walk_forward_analysis(payload: dict):
    """
    Perform walk-forward analysis.
    
    Request body:
    - ticker: str (required)
    - historical_data: list[dict] (required)
    - train_size: int (optional, default: 60) - bars for training
    - test_size: int (optional, default: 20) - bars for testing
    - config: dict (optional) - base configuration
    """
    from app.services.mirofish import walk_forward_analysis as wfa
    
    ticker = payload.get("ticker")
    historical_data = payload.get("historical_data")
    
    if not all([ticker, historical_data]):
        raise HTTPException(status_code=400, detail="ticker and historical_data are required")
    
    return await wfa(
        ticker=ticker,
        historical_data=historical_data,
        train_size=payload.get("train_size", 60),
        test_size=payload.get("test_size", 20),
        config=payload.get("config"),
    )


@router.get("/comparison")
async def compare_signals(
    ticker: str,
    timeframe: str = "5m",
    sources: str | None = None,
):
    """
    Compare MiroFish signals with other signal sources.
    
    Query parameters:
    - ticker: str (required)
    - timeframe: str (optional, default: "5m")
    - sources: str (optional) - comma-separated list of sources to include
      (default: mirofish,technical,sentiment,market_regime)
    
    Returns:
    - Signal comparison across sources
    - Agreement/disagreement analysis
    - Consensus bias and confidence
    - Accuracy ranking of sources
    """
    from app.services.mirofish import compare_signals as compare
    
    include_sources = None
    if sources:
        include_sources = [s.strip() for s in sources.split(",")]
    
    return await compare(
        ticker=ticker,
        timeframe=timeframe,
        include_sources=include_sources,
    )


@router.get("/comparison/accuracy/{ticker}")
async def get_accuracy_ranking(ticker: str):
    """
    Get accuracy ranking for signal sources on a specific ticker.
    
    Returns historical accuracy data for MiroFish vs other sources.
    """
    from app.services.mirofish import get_accuracy_ranking as get_ranking
    
    return {
        "ticker": ticker.upper(),
        "accuracy_ranking": await get_ranking(ticker),
    }


@router.post("/comparison/record-outcome")
async def record_outcome(payload: dict):
    """
    Record the outcome of a prediction for accuracy tracking.
    
    Request body:
    - prediction_id: str (required)
    - ticker: str (required)
    - source: str (required) - "mirofish", "technical", etc.
    - predicted_bias: str (required) - "BULLISH", "BEARISH", or "NEUTRAL"
    - predicted_confidence: float (required)
    - actual_return: float (required) - actual return over holding period
    - resolution_price: float (required) - price when resolved
    - holding_days: int (optional, default: 5)
    """
    from app.services.mirofish import record_prediction_outcome
    
    required = ["prediction_id", "ticker", "source", "predicted_bias", 
                "predicted_confidence", "actual_return", "resolution_price"]
    
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    await record_prediction_outcome(
        prediction_id=payload["prediction_id"],
        ticker=payload["ticker"],
        source=payload["source"],
        predicted_bias=payload["predicted_bias"],
        predicted_confidence=payload["predicted_confidence"],
        actual_return=payload["actual_return"],
        resolution_price=payload["resolution_price"],
        holding_days=payload.get("holding_days", 5),
    )
    
    return {"status": "recorded", "prediction_id": payload["prediction_id"]}


# Practice Mode Endpoints

@router.post("/practice/session/create")
async def practice_create_session(payload: dict):
    """
    Create a new practice trading session.
    
    Request body:
    - name: str (required)
    - config_name: str (optional, default: "balanced")
    - initial_capital: float (optional, default: 100000)
    - description: str (optional)
    """
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    
    return await create_practice_session(
        name=name,
        config_name=payload.get("config_name", "balanced"),
        initial_capital=payload.get("initial_capital", 100000.0),
    )


@router.get("/practice/configs")
async def practice_configs():
    """Get available practice configurations."""
    return get_available_configs()


@router.post("/practice/evaluate-entry")
async def practice_evaluate_entry(payload: dict):
    """
    Evaluate whether to enter a trade.
    
    Request body:
    - session_id: str (required)
    - ticker: str (required)
    - current_price: float (required)
    """
    session_id = payload.get("session_id")
    ticker = payload.get("ticker")
    current_price = payload.get("current_price")
    
    if not all([session_id, ticker, current_price]):
        raise HTTPException(status_code=400, detail="session_id, ticker, and current_price are required")
    
    return await evaluate_trade_entry(session_id, ticker, float(current_price))


@router.post("/practice/trade/enter")
async def practice_enter_trade(payload: dict):
    """
    Enter a practice trade.
    
    Request body:
    - session_id: str (required)
    - ticker: str (required)
    - direction: str (required) - "LONG" or "SHORT"
    - entry_price: float (required)
    - quantity: int (required)
    - signal: dict (optional) - MiroFish signal that triggered trade
    """
    session_id = payload.get("session_id")
    ticker = payload.get("ticker")
    direction = payload.get("direction")
    entry_price = payload.get("entry_price")
    quantity = payload.get("quantity")
    
    if not all([session_id, ticker, direction, entry_price, quantity]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    try:
        direction_enum = TradeDirection(direction.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="direction must be LONG or SHORT")
    
    return await simulate_trade(
        session_id=session_id,
        ticker=ticker,
        direction=direction_enum.value,
        entry_price=float(entry_price),
        quantity=int(quantity),
        signal=payload.get("signal"),
    )


@router.post("/practice/trade/exit")
async def practice_exit_trade(payload: dict):
    """
    Exit a practice trade.
    
    Request body:
    - session_id: str (required)
    - trade_id: str (required)
    - exit_price: float (required)
    - exit_reason: str (required) - "target_hit", "stop_loss", "signal_reversal", "time_expired", "manual", "max_hold_time"
    """
    session_id = payload.get("session_id")
    trade_id = payload.get("trade_id")
    exit_price = payload.get("exit_price")
    exit_reason = payload.get("exit_reason")
    
    if not all([session_id, trade_id, exit_price, exit_reason]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    try:
        reason_enum = ExitReason(exit_reason.lower())
    except ValueError:
        valid_reasons = [r.value for r in ExitReason]
        raise HTTPException(status_code=400, detail=f"exit_reason must be one of: {valid_reasons}")
    
    return await close_trade(
        session_id=session_id,
        trade_id=trade_id,
        exit_price=float(exit_price),
        exit_reason=reason_enum.value,
    )


@router.post("/practice/session/results")
async def practice_session_results(payload: dict):
    """
    Get results for a practice session.
    
    Request body:
    - session_id: str (required)
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    return get_session_results(session_id)


@router.get("/practice/sessions")
async def practice_list_sessions():
    """List all active practice sessions."""
    practice = get_practice()
    return {
        "sessions": [
            session.to_dict()
            for session in practice.sessions.values()
        ]
    }


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/analytics/accuracy")
async def analytics_accuracy(
    days: int = 30,
    ticker: str | None = None,
    timeframe: str | None = None,
):
    """
    Get overall accuracy statistics for MiroFish predictions.
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    - ticker: str (optional) - Filter by specific ticker
    - timeframe: str (optional) - Filter by specific timeframe (e.g., "5m", "1h")
    
    Returns:
    - total_predictions: Total number of predictions analyzed
    - correct_predictions: Number of correct predictions
    - accuracy_rate: Overall accuracy rate (0-1)
    - by_signal_type: Accuracy breakdown by signal type (LONG, SHORT, NEUTRAL)
    - by_ticker: Accuracy breakdown by ticker
    - by_timeframe: Accuracy breakdown by timeframe
    - confidence_calibration: Does high confidence = high accuracy?
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    metrics = analytics.get_overall_accuracy(days=days, ticker=ticker, timeframe=timeframe)
    
    return {
        "period_days": days,
        "filters": {
            "ticker": ticker,
            "timeframe": timeframe,
        },
        "metrics": metrics.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/ticker/{ticker}")
async def analytics_ticker(
    ticker: str,
    days: int = 30,
):
    """
    Get detailed analytics for a specific ticker.
    
    Path parameters:
    - ticker: str (required) - Stock symbol
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    
    Returns:
    - ticker: The ticker symbol
    - period_days: Analysis period
    - accuracy: Full accuracy metrics
    - signal_distribution: Distribution of signal types
    - total_predictions: Total predictions for this ticker
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    result = analytics.get_ticker_accuracy(ticker=ticker, days=days)
    
    return {
        **result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/timeframe/{timeframe}")
async def analytics_timeframe(
    timeframe: str,
    days: int = 30,
):
    """
    Get analytics for a specific timeframe.
    
    Path parameters:
    - timeframe: str (required) - Timeframe (e.g., "5m", "15m", "1h", "1d")
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    
    Returns:
    - timeframe: The timeframe analyzed
    - period_days: Analysis period
    - accuracy: Full accuracy metrics
    - avg_time_to_resolution_hours: Average time to resolve predictions
    - total_predictions: Total predictions for this timeframe
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    result = analytics.get_timeframe_accuracy(timeframe=timeframe, days=days)
    
    return {
        **result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/timeline/{ticker}")
async def analytics_timeline(
    ticker: str,
    days: int = 30,
):
    """
    Get historical predictions timeline for a ticker.
    
    Path parameters:
    - ticker: str (required) - Stock symbol
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    
    Returns:
    - prediction_trend: Daily signal counts over time
    - confidence_evolution: How confidence has changed
    - signal_strength_timeline: Signal strength over time
    - accuracy_over_time: Rolling window accuracy
    - multi_timeframe_alignment: How aligned different timeframes are
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    analysis = analytics.get_time_series_analysis(ticker=ticker, days=days)
    
    return {
        "ticker": ticker.upper(),
        "period_days": days,
        "analysis": analysis.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/confidence")
async def analytics_confidence(
    days: int = 30,
    ticker: str | None = None,
):
    """
    Get confidence calibration analysis.
    
    Analyzes whether MiroFish's confidence scores are well-calibrated
    (i.e., does 80% confidence actually mean 80% accuracy?).
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    - ticker: str (optional) - Filter by specific ticker
    
    Returns:
    - confidence_bins: Accuracy broken down by confidence ranges
    - calibration_score: How well-calibrated the model is (0-1)
    - overconfidence_detected: Whether model is overconfident
    - underconfidence_detected: Whether model is underconfident
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    metrics = analytics.get_overall_accuracy(days=days, ticker=ticker)
    
    calibration = metrics.confidence_calibration
    
    # Calculate calibration score
    total_error = 0.0
    total_weight = 0
    for bin_key, data in calibration.items():
        if data["total"] > 0:
            expected = data["avg_confidence"]
            actual = data["accuracy"]
            weight = data["total"]
            total_error += abs(expected - actual) * weight
            total_weight += weight
    
    calibration_score = 1.0 - (total_error / total_weight) if total_weight > 0 else 0.0
    
    # Detect over/under confidence
    overconfident_bins = 0
    underconfident_bins = 0
    for bin_key, data in calibration.items():
        if data["total"] >= 5:  # Minimum sample size
            if data["accuracy"] < data["avg_confidence"] - 0.1:
                overconfident_bins += 1
            elif data["accuracy"] > data["avg_confidence"] + 0.1:
                underconfident_bins += 1
    
    return {
        "period_days": days,
        "ticker": ticker,
        "calibration": calibration,
        "calibration_score": round(calibration_score, 4),
        "overconfidence_detected": overconfident_bins >= 2,
        "underconfidence_detected": underconfident_bins >= 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/performance")
async def analytics_performance(
    days: int = 30,
    ticker: str | None = None,
    signal_type: str | None = None,
):
    """
    Get comprehensive performance metrics.
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    - ticker: str (optional) - Filter by specific ticker
    - signal_type: str (optional) - Filter by signal type (LONG, SHORT, NEUTRAL)
    
    Returns:
    - total_signals: Total number of signals
    - winning_signals: Number of winning signals
    - losing_signals: Number of losing signals
    - win_rate: Win rate (0-1)
    - average_return: Average return per signal
    - total_return: Cumulative return
    - sharpe_ratio: Risk-adjusted return metric
    - max_drawdown: Maximum drawdown amount
    - max_drawdown_pct: Maximum drawdown percentage
    - profit_factor: Gross profit / gross loss
    - best_ticker: Best performing ticker
    - worst_ticker: Worst performing ticker
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    metrics = analytics.get_performance_metrics(
        ticker=ticker,
        signal_type=signal_type,
        days=days,
    )
    
    return {
        "period_days": days,
        "filters": {
            "ticker": ticker,
            "signal_type": signal_type,
        },
        "metrics": metrics.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/signal-types")
async def analytics_signal_types(
    days: int = 30,
):
    """
    Get performance breakdown by signal type (LONG, SHORT, NEUTRAL).
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    
    Returns:
    - by_signal_type: Performance metrics for each signal type
    - period_days: Analysis period
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    result = analytics.get_signal_type_performance(days=days)
    
    return {
        **result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/visualization")
async def analytics_visualization(
    days: int = 30,
    ticker: str | None = None,
):
    """
    Get data formatted for visualization.
    
    Query parameters:
    - days: int (optional, default: 30) - Number of days to look back
    - ticker: str (optional) - Filter by specific ticker
    
    Returns:
    - accuracy_heatmap: Data for ticker x timeframe heatmap
    - confidence_distribution: Histogram of confidence scores
    - signal_timeline: Chronological list of all signals
    - price_correlation: Correlation between predictions and price movements
    """
    from app.services.mirofish.analytics import get_analytics
    
    analytics = get_analytics()
    viz_data = analytics.get_visualization_data(ticker=ticker, days=days)
    
    return {
        "period_days": days,
        "ticker": ticker,
        "visualization": viz_data.to_dict(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/analytics/store-prediction")
async def store_prediction_endpoint(payload: dict):
    """
    Store a new MiroFish prediction for tracking.
    
    This endpoint should be called whenever MiroFish generates a prediction.
    
    Request body:
    - ticker: str (required)
    - signal_type: str (required) - LONG, SHORT, NEUTRAL, etc.
    - confidence: float (required) - 0-1 confidence score
    - timeframe: str (required) - 5m, 1h, 1d, etc.
    - lens: str (optional, default: "overall") - trend, momentum, etc.
    - metadata: dict (optional) - Additional prediction metadata
    - price_at_prediction: float (optional) - Current price when predicted
    
    Returns:
    - prediction_id: ID of stored prediction
    - status: "stored"
    """
    from app.services.mirofish.analytics import store_prediction
    
    required = ["ticker", "signal_type", "confidence", "timeframe"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    prediction = store_prediction(
        ticker=payload["ticker"],
        signal_type=payload["signal_type"],
        confidence=payload["confidence"],
        timeframe=payload["timeframe"],
        lens=payload.get("lens", "overall"),
        metadata=payload.get("metadata"),
        price_at_prediction=payload.get("price_at_prediction"),
    )
    
    return {
        "prediction_id": prediction.id,
        "status": "stored",
        "ticker": prediction.ticker,
        "signal_type": prediction.signal_type,
        "predicted_at": prediction.predicted_at.isoformat(),
    }


@router.post("/analytics/record-outcome")
async def record_outcome_endpoint(payload: dict):
    """
    Record the outcome of a prediction.
    
    This endpoint should be called when a prediction's outcome is known.
    
    Request body:
    - prediction_id: int (required) - ID from store-prediction
    - actual_return: float (required) - Actual return achieved
    - outcome_price: float (required) - Price at outcome time
    - outcome_time: str (optional) - ISO timestamp
    - was_correct: bool (optional) - Auto-calculated if not provided
    - metadata: dict (optional) - Additional outcome metadata
    
    Returns:
    - outcome_id: ID of recorded outcome
    - status: "recorded"
    """
    from app.services.mirofish.analytics import record_outcome
    from datetime import datetime
    
    required = ["prediction_id", "actual_return", "outcome_price"]
    for field in required:
        if field not in payload:
            raise HTTPException(status_code=400, detail=f"{field} is required")
    
    outcome_time = None
    if payload.get("outcome_time"):
        outcome_time = datetime.fromisoformat(payload["outcome_time"])
    
    outcome = record_outcome(
        prediction_id=payload["prediction_id"],
        actual_return=payload["actual_return"],
        outcome_price=payload["outcome_price"],
        outcome_time=outcome_time,
        was_correct=payload.get("was_correct"),
        metadata=payload.get("metadata"),
    )
    
    return {
        "outcome_id": outcome.id,
        "status": "recorded",
        "prediction_id": outcome.prediction_id,
        "was_correct": outcome.was_correct,
        "actual_return": outcome.actual_return,
    }
