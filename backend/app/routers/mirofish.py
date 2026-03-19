from fastapi import APIRouter, HTTPException

from app.services.mirofish import (
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
