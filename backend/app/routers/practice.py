"""Practice Trading API Router.

Provides REST endpoints for paper trading operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.practice import (
    get_practice_engine,
    get_strategy,
    list_available_strategies,
    get_practice_evaluator,
    get_challenge_manager,
    StrategySignal,
)

router = APIRouter(prefix="/practice", tags=["practice"])


# Request/Response Models
class PortfolioCreateRequest(BaseModel):
    user_id: str
    initial_balance: float = Field(default=100000.0, gt=0)


class TradeRequest(BaseModel):
    user_id: str
    ticker: str
    side: str  # buy, sell
    quantity: float = Field(gt=0)
    market_price: float = Field(gt=0)
    strategy_id: str | None = None
    rationale: dict[str, Any] | None = None


class StrategyAnalyzeRequest(BaseModel):
    ticker: str
    portfolio_value: float = Field(default=100000.0, gt=0)
    context: dict[str, Any] | None = None


class ChallengeProgressRequest(BaseModel):
    user_id: str
    challenge_id: str
    progress: dict[str, Any]


# Portfolio Endpoints
@router.post("/portfolio/create")
async def create_portfolio(
    request: PortfolioCreateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new practice portfolio."""
    engine = get_practice_engine(db)
    portfolio = engine.create_portfolio(
        user_id=request.user_id,
        initial_balance=Decimal(str(request.initial_balance)),
    )
    return engine.get_portfolio_summary(request.user_id)


@router.get("/portfolio/{user_id}")
async def get_portfolio(
    user_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get portfolio summary."""
    engine = get_practice_engine(db)
    summary = engine.get_portfolio_summary(user_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail=summary["error"])
    return summary


@router.post("/portfolio/{user_id}/reset")
async def reset_portfolio(
    user_id: str,
    new_balance: float | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reset portfolio to initial state."""
    engine = get_practice_engine(db)
    balance = Decimal(str(new_balance)) if new_balance else None
    engine.reset_portfolio(user_id, balance)
    return engine.get_portfolio_summary(user_id)


# Trading Endpoints
@router.post("/trade/execute")
async def execute_trade(
    request: TradeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a paper trade."""
    engine = get_practice_engine(db)
    
    try:
        trade = await engine.execute_trade(
            user_id=request.user_id,
            ticker=request.ticker,
            side=request.side,
            quantity=Decimal(str(request.quantity)),
            market_price=Decimal(str(request.market_price)),
            strategy_id=request.strategy_id,
            rationale=request.rationale,
        )
        
        # Check challenges
        challenge_manager = get_challenge_manager(db)
        challenge_manager.check_trade_challenges(
            request.user_id,
            {
                "ticker": request.ticker,
                "side": request.side,
                "pnl": float(trade.rationale.get("realized_pnl", 0)) if trade.rationale else 0,
            }
        )
        
        return {
            "trade_id": trade.trade_id,
            "status": trade.status.value,
            "ticker": trade.ticker,
            "side": trade.side,
            "quantity": str(trade.quantity),
            "price": str(trade.price),
            "commission": str(trade.commission),
            "slippage": str(trade.slippage),
            "total_cost": str(trade.total_cost),
            "filled_at": trade.filled_at.isoformat() if trade.filled_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trade/close-all/{user_id}")
async def close_all_positions(
    user_id: str,
    market_prices: dict[str, float],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Close all open positions."""
    engine = get_practice_engine(db)
    prices = {k: Decimal(str(v)) for k, v in market_prices.items()}
    trades = engine.close_all_positions(user_id, prices)
    
    return {
        "closed_positions": len(trades),
        "trades": [
            {
                "trade_id": t.trade_id,
                "ticker": t.ticker,
                "side": t.side,
                "quantity": str(t.quantity),
                "price": str(t.price),
            }
            for t in trades
        ],
    }


# Strategy Endpoints
@router.get("/strategies")
async def get_available_strategies() -> list[dict[str, Any]]:
    """List all available trading strategies."""
    return list_available_strategies()


@router.post("/strategy/{strategy_type}/analyze")
async def analyze_with_strategy(
    strategy_type: str,
    request: StrategyAnalyzeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Analyze a ticker using a specific strategy."""
    try:
        strategy = get_strategy(strategy_type)
        recommendation = await strategy.analyze(
            ticker=request.ticker,
            context={
                "portfolio_value": request.portfolio_value,
                **(request.context or {}),
            },
        )
        
        return {
            "ticker": recommendation.ticker,
            "signal": recommendation.signal.value,
            "confidence": recommendation.confidence,
            "suggested_position_size": str(recommendation.suggested_position_size),
            "is_actionable": recommendation.is_actionable,
            "rationale": recommendation.rationale,
            "strategy_name": recommendation.strategy_name,
            "metadata": recommendation.metadata,
            "timestamp": recommendation.timestamp.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Evaluation Endpoints
@router.get("/evaluation/{user_id}/win-rate")
async def get_win_rate(
    user_id: str,
    strategy_id: str | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get win rate statistics."""
    evaluator = get_practice_evaluator(db)
    from datetime import datetime, timezone, timedelta
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    return evaluator.calculate_win_rate(user_id, strategy_id, start_date, end_date)


@router.get("/evaluation/{user_id}/sharpe")
async def get_sharpe_ratio(
    user_id: str,
    strategy_id: str | None = None,
    days: int = 30,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get Sharpe ratio."""
    evaluator = get_practice_evaluator(db)
    return evaluator.calculate_sharpe_ratio(user_id, strategy_id, days)


@router.get("/evaluation/{user_id}/drawdowns")
async def get_drawdowns(
    user_id: str,
    strategy_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get drawdown analysis."""
    evaluator = get_practice_evaluator(db)
    return evaluator.analyze_drawdowns(user_id, strategy_id)


@router.get("/evaluation/{user_id}/summary")
async def get_performance_summary(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get comprehensive performance summary."""
    evaluator = get_practice_evaluator(db)
    return evaluator.get_performance_summary(user_id, days)


@router.get("/evaluation/{user_id}/compare-strategies")
async def compare_strategies(
    user_id: str,
    days: int = 30,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Compare performance across strategies."""
    evaluator = get_practice_evaluator(db)
    from datetime import datetime, timezone, timedelta
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    return evaluator.compare_strategies(user_id, None, start_date, end_date)


# Challenge Endpoints
@router.post("/challenges/{user_id}/daily")
async def generate_daily_challenges(
    user_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Generate daily challenges for user."""
    manager = get_challenge_manager(db)
    challenge_set = manager.generate_daily_challenges(user_id)
    
    return {
        "date": challenge_set.date,
        "challenges": [
            {
                "challenge_id": c.challenge_id,
                "name": c.name,
                "description": c.description,
                "type": c.challenge_type.value,
                "reward_points": c.reward_points,
                "progress_percent": c.progress_percent,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            }
            for c in challenge_set.challenges
        ],
    }


@router.get("/challenges/{user_id}/active")
async def get_active_challenges(
    user_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get active challenges for user."""
    manager = get_challenge_manager(db)
    challenges = manager.get_active_challenges(user_id)
    
    return [
        {
            "challenge_id": c.challenge_id,
            "name": c.name,
            "description": c.description,
            "type": c.challenge_type.value,
            "reward_points": c.reward_points,
            "progress_percent": c.progress_percent,
            "progress": c.progress,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        }
        for c in challenges
    ]


@router.post("/challenges/{user_id}/progress")
async def update_challenge_progress(
    user_id: str,
    request: ChallengeProgressRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update challenge progress."""
    manager = get_challenge_manager(db)
    challenge = manager.update_challenge_progress(
        user_id=request.user_id,
        challenge_id=request.challenge_id,
        progress_update=request.progress,
    )
    
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    return {
        "challenge_id": challenge.challenge_id,
        "status": challenge.status.value,
        "progress_percent": challenge.progress_percent,
        "completed_at": challenge.completed_at.isoformat() if challenge.completed_at else None,
    }


@router.get("/achievements/{user_id}")
async def get_user_achievements(
    user_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get user achievements and points."""
    manager = get_challenge_manager(db)
    achievements = manager.get_user_achievements(user_id)
    points = manager.get_user_points(user_id)
    
    return {
        "total_points": points,
        "achievements": [
            {
                "achievement_id": a.achievement_id,
                "name": a.name,
                "description": a.description,
                "tier": a.tier.value,
                "icon": a.icon,
                "earned_at": a.earned_at.isoformat(),
            }
            for a in achievements
        ],
    }


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 10,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get practice trading leaderboard."""
    manager = get_challenge_manager(db)
    return manager.get_leaderboard(limit)
