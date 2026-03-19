"""Practice Trading Evaluation - Performance tracking and analysis.

This module provides win rate tracking, Sharpe ratio calculation,
drawdown analysis, and strategy comparison for practice trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import math
from collections import defaultdict

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.models.entities import PaperOrder


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAK_EVEN = "break_even"


@dataclass
class TradePerformance:
    """Performance metrics for a single trade."""
    
    trade_id: str
    ticker: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    side: str
    pnl: Decimal
    pnl_percent: Decimal
    outcome: TradeOutcome
    entry_time: datetime
    exit_time: datetime | None
    duration_minutes: float | None
    strategy_id: str | None = None


@dataclass
class PeriodPerformance:
    """Performance metrics for a specific time period."""
    
    period_start: datetime
    period_end: datetime
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    total_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    gross_profit: Decimal = field(default_factory=lambda: Decimal("0"))
    gross_loss: Decimal = field(default_factory=lambda: Decimal("0"))
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate as percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        if self.gross_loss == 0:
            return float("inf") if self.gross_profit > 0 else 0.0
        return float(self.gross_profit / abs(self.gross_loss))
    
    @property
    def average_win(self) -> Decimal:
        """Calculate average winning trade P&L."""
        if self.winning_trades == 0:
            return Decimal("0")
        return self.gross_profit / self.winning_trades
    
    @property
    def average_loss(self) -> Decimal:
        """Calculate average losing trade P&L."""
        if self.losing_trades == 0:
            return Decimal("0")
        return self.gross_loss / self.losing_trades
    
    @property
    def expectancy(self) -> Decimal:
        """Calculate expectancy (average P&L per trade)."""
        if self.total_trades == 0:
            return Decimal("0")
        return self.total_pnl / self.total_trades


@dataclass
class DrawdownPeriod:
    """Represents a drawdown period in the equity curve."""
    
    start_time: datetime
    end_time: datetime | None
    peak_equity: Decimal
    trough_equity: Decimal
    recovery_equity: Decimal | None
    
    @property
    def drawdown_amount(self) -> Decimal:
        """Calculate drawdown amount."""
        return self.peak_equity - self.trough_equity
    
    @property
    def drawdown_percent(self) -> float:
        """Calculate drawdown as percentage of peak."""
        if self.peak_equity == 0:
            return 0.0
        return float((self.drawdown_amount / self.peak_equity) * 100)
    
    @property
    def duration(self) -> timedelta | None:
        """Calculate duration of drawdown."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_recovered(self) -> bool:
        """Check if drawdown has been recovered."""
        return self.recovery_equity is not None and self.recovery_equity >= self.peak_equity


@dataclass
class StrategyComparison:
    """Comparison metrics between strategies."""
    
    strategy_id: str
    strategy_name: str
    total_trades: int
    win_rate: float
    total_pnl: Decimal
    sharpe_ratio: float
    max_drawdown_percent: float
    profit_factor: float
    avg_trade_duration: float  # minutes
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl": str(self.total_pnl),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown_percent": round(self.max_drawdown_percent, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_trade_duration_minutes": round(self.avg_trade_duration, 2),
        }


class PracticeEvaluator:
    """Evaluator for practice trading performance."""
    
    # Risk-free rate for Sharpe calculation (annual)
    RISK_FREE_RATE = 0.02
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_win_rate(
        self,
        user_id: str,
        strategy_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate win rate for a user's trades."""
        trades = self._get_closed_trades(user_id, strategy_id, start_date, end_date)
        
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "break_even_trades": 0,
                "win_rate": 0.0,
                "loss_rate": 0.0,
                "break_even_rate": 0.0,
            }
        
        wins = sum(1 for t in trades if t.outcome == TradeOutcome.WIN)
        losses = sum(1 for t in trades if t.outcome == TradeOutcome.LOSS)
        break_evens = sum(1 for t in trades if t.outcome == TradeOutcome.BREAK_EVEN)
        total = len(trades)
        
        return {
            "total_trades": total,
            "winning_trades": wins,
            "losing_trades": losses,
            "break_even_trades": break_evens,
            "win_rate": round((wins / total) * 100, 2),
            "loss_rate": round((losses / total) * 100, 2),
            "break_even_rate": round((break_evens / total) * 100, 2),
        }
    
    def calculate_sharpe_ratio(
        self,
        user_id: str,
        strategy_id: str | None = None,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Calculate Sharpe ratio for a user's trading performance."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        # Get daily returns
        daily_returns = self._get_daily_returns(user_id, strategy_id, start_date, end_date)
        
        if len(daily_returns) < 2:
            return {
                "sharpe_ratio": 0.0,
                "annualized_return": 0.0,
                "annualized_volatility": 0.0,
                "risk_free_rate": self.RISK_FREE_RATE,
                "period_days": period_days,
                "data_points": len(daily_returns),
            }
        
        # Calculate average daily return
        avg_return = sum(daily_returns) / len(daily_returns)
        
        # Calculate standard deviation
        variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            sharpe = 0.0
        else:
            # Daily risk-free rate
            daily_rf = self.RISK_FREE_RATE / 252  # Trading days per year
            sharpe = (avg_return - daily_rf) / std_dev
        
        # Annualize
        annualized_return = avg_return * 252
        annualized_volatility = std_dev * math.sqrt(252)
        annualized_sharpe = sharpe * math.sqrt(252)
        
        return {
            "sharpe_ratio": round(sharpe, 4),
            "annualized_sharpe_ratio": round(annualized_sharpe, 4),
            "annualized_return": round(annualized_return * 100, 2),  # As percentage
            "annualized_volatility": round(annualized_volatility * 100, 2),  # As percentage
            "risk_free_rate": self.RISK_FREE_RATE * 100,  # As percentage
            "period_days": period_days,
            "data_points": len(daily_returns),
            "avg_daily_return": round(avg_return * 100, 4),
        }
    
    def analyze_drawdowns(
        self,
        user_id: str,
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        """Analyze drawdown periods in trading history."""
        equity_curve = self._get_equity_curve(user_id, strategy_id)
        
        if len(equity_curve) < 2:
            return {
                "max_drawdown_percent": 0.0,
                "max_drawdown_amount": "0",
                "avg_drawdown_percent": 0.0,
                "total_drawdowns": 0,
                "current_drawdown_percent": 0.0,
                "drawdown_periods": [],
            }
        
        drawdowns = self._calculate_drawdown_periods(equity_curve)
        
        if not drawdowns:
            return {
                "max_drawdown_percent": 0.0,
                "max_drawdown_amount": "0",
                "avg_drawdown_percent": 0.0,
                "total_drawdowns": 0,
                "current_drawdown_percent": 0.0,
                "drawdown_periods": [],
            }
        
        max_dd = max(drawdowns, key=lambda x: x.drawdown_percent)
        avg_dd = sum(d.drawdown_percent for d in drawdowns) / len(drawdowns)
        
        # Check current drawdown
        current_equity = equity_curve[-1]["equity"]
        peak_equity = max(e["equity"] for e in equity_curve)
        current_dd = ((peak_equity - current_equity) / peak_equity * 100) if peak_equity > 0 else 0
        
        return {
            "max_drawdown_percent": round(max_dd.drawdown_percent, 2),
            "max_drawdown_amount": str(max_dd.drawdown_amount),
            "avg_drawdown_percent": round(avg_dd, 2),
            "total_drawdowns": len(drawdowns),
            "current_drawdown_percent": round(current_dd, 2),
            "drawdown_periods": [
                {
                    "start": dd.start_time.isoformat(),
                    "end": dd.end_time.isoformat() if dd.end_time else None,
                    "peak_equity": str(dd.peak_equity),
                    "trough_equity": str(dd.trough_equity),
                    "drawdown_percent": round(dd.drawdown_percent, 2),
                    "duration_hours": round(dd.duration.total_seconds() / 3600, 2) if dd.duration else None,
                    "recovered": dd.is_recovered,
                }
                for dd in drawdowns
            ],
        }
    
    def compare_strategies(
        self,
        user_id: str,
        strategy_ids: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Compare performance across multiple strategies."""
        if strategy_ids is None:
            # Get all strategies used by user
            strategy_ids = self._get_user_strategies(user_id)
        
        comparisons = []
        
        for strategy_id in strategy_ids:
            try:
                comparison = self._analyze_strategy(
                    user_id, strategy_id, start_date, end_date
                )
                comparisons.append(comparison.to_dict())
            except Exception as e:
                comparisons.append({
                    "strategy_id": strategy_id,
                    "error": str(e),
                })
        
        # Sort by total P&L
        comparisons.sort(
            key=lambda x: Decimal(x.get("total_pnl", "0")) if "total_pnl" in x else Decimal("-999999"),
            reverse=True
        )
        
        return comparisons
    
    def get_performance_summary(
        self,
        user_id: str,
        period_days: int = 30,
    ) -> dict[str, Any]:
        """Get comprehensive performance summary."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=period_days)
        
        win_rate_data = self.calculate_win_rate(user_id, None, start_date, end_date)
        sharpe_data = self.calculate_sharpe_ratio(user_id, None, period_days)
        drawdown_data = self.analyze_drawdowns(user_id, None)
        
        # Get period performance
        period_perf = self._calculate_period_performance(user_id, None, start_date, end_date)
        
        return {
            "period_days": period_days,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "win_rate": win_rate_data,
            "sharpe_ratio": sharpe_data,
            "drawdowns": drawdown_data,
            "period_performance": {
                "total_trades": period_perf.total_trades,
                "total_pnl": str(period_perf.total_pnl),
                "win_rate": round(period_perf.win_rate, 2),
                "profit_factor": round(period_perf.profit_factor, 2),
                "expectancy": str(period_perf.expectancy),
                "average_win": str(period_perf.average_win),
                "average_loss": str(period_perf.average_loss),
            },
        }
    
    def _get_closed_trades(
        self,
        user_id: str,
        strategy_id: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[TradePerformance]:
        """Get closed trades from database."""
        query = select(PaperOrder).where(PaperOrder.status == "filled")
        
        # Filter by user (stored in rationale)
        # Note: This assumes user_id is stored in rationale JSON
        
        if start_date:
            query = query.where(PaperOrder.created_at >= start_date)
        if end_date:
            query = query.where(PaperOrder.created_at <= end_date)
        
        orders = self.db.scalars(query).all()
        
        trades = []
        for order in orders:
            rationale = order.rationale or {}
            
            # Filter by user_id if provided
            order_user_id = rationale.get("user_id")
            if user_id and order_user_id != user_id:
                continue
            
            # Filter by strategy_id if provided
            order_strategy_id = rationale.get("strategy_id")
            if strategy_id and order_strategy_id != strategy_id:
                continue
            
            # Parse P&L from rationale if available
            pnl = Decimal(str(rationale.get("realized_pnl", 0)))
            
            # Determine outcome
            if pnl > Decimal("0.01"):
                outcome = TradeOutcome.WIN
            elif pnl < Decimal("-0.01"):
                outcome = TradeOutcome.LOSS
            else:
                outcome = TradeOutcome.BREAK_EVEN
            
            trade = TradePerformance(
                trade_id=order.broker_order_id or str(order.id),
                ticker=order.ticker,
                entry_price=Decimal(str(rationale.get("entry_price", 0))),
                exit_price=Decimal(str(rationale.get("exit_price", 0))),
                quantity=Decimal(str(order.qty or 0)),
                side=order.side,
                pnl=pnl,
                pnl_percent=Decimal(str(rationale.get("pnl_percent", 0))),
                outcome=outcome,
                entry_time=order.created_at,
                exit_time=order.created_at,  # Simplified
                duration_minutes=rationale.get("duration_minutes"),
                strategy_id=order_strategy_id,
            )
            trades.append(trade)
        
        return trades
    
    def _get_daily_returns(
        self,
        user_id: str,
        strategy_id: str | None,
        start_date: datetime,
        end_date: datetime,
    ) -> list[float]:
        """Get daily returns for Sharpe calculation."""
        # Get all trades in period
        trades = self._get_closed_trades(user_id, strategy_id, start_date, end_date)
        
        # Group by day
        daily_pnl: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        
        for trade in trades:
            day_key = trade.exit_time.strftime("%Y-%m-%d") if trade.exit_time else "unknown"
            daily_pnl[day_key] += trade.pnl
        
        # Convert to returns (assuming fixed capital for simplicity)
        # In practice, you'd use actual portfolio value
        assumed_capital = Decimal("100000")
        returns = [float(pnl / assumed_capital) for pnl in daily_pnl.values()]
        
        return returns
    
    def _get_equity_curve(
        self,
        user_id: str,
        strategy_id: str | None,
    ) -> list[dict[str, Any]]:
        """Get equity curve over time."""
        trades = self._get_closed_trades(user_id, strategy_id, None, None)
        
        if not trades:
            return []
        
        # Sort by exit time
        trades.sort(key=lambda x: x.exit_time or x.entry_time)
        
        # Build equity curve
        initial_equity = Decimal("100000")
        equity = initial_equity
        curve = [{"time": trades[0].entry_time, "equity": equity}]
        
        for trade in trades:
            equity += trade.pnl
            curve.append({
                "time": trade.exit_time or trade.entry_time,
                "equity": equity,
            })
        
        return curve
    
    def _calculate_drawdown_periods(
        self,
        equity_curve: list[dict[str, Any]],
    ) -> list[DrawdownPeriod]:
        """Calculate drawdown periods from equity curve."""
        if len(equity_curve) < 2:
            return []
        
        drawdowns = []
        peak = equity_curve[0]["equity"]
        peak_time = equity_curve[0]["time"]
        trough = peak
        trough_time = peak_time
        in_drawdown = False
        
        for point in equity_curve[1:]:
            equity = point["equity"]
            time = point["time"]
            
            if equity > peak:
                # End of drawdown
                if in_drawdown:
                    drawdowns.append(DrawdownPeriod(
                        start_time=peak_time,
                        end_time=time,
                        peak_equity=peak,
                        trough_equity=trough,
                        recovery_equity=equity,
                    ))
                
                peak = equity
                peak_time = time
                trough = equity
                trough_time = time
                in_drawdown = False
            
            elif equity < trough:
                trough = equity
                trough_time = time
                in_drawdown = True
        
        # Handle ongoing drawdown
        if in_drawdown:
            drawdowns.append(DrawdownPeriod(
                start_time=peak_time,
                end_time=None,
                peak_equity=peak,
                trough_equity=trough,
                recovery_equity=None,
            ))
        
        return drawdowns
    
    def _get_user_strategies(self, user_id: str) -> list[str]:
        """Get list of strategies used by user."""
        query = select(PaperOrder).where(PaperOrder.status == "filled")
        orders = self.db.scalars(query).all()
        
        strategies = set()
        for order in orders:
            rationale = order.rationale or {}
            if rationale.get("user_id") == user_id:
                strategy_id = rationale.get("strategy_id")
                if strategy_id:
                    strategies.add(strategy_id)
        
        return list(strategies)
    
    def _analyze_strategy(
        self,
        user_id: str,
        strategy_id: str,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> StrategyComparison:
        """Analyze a single strategy's performance."""
        trades = self._get_closed_trades(user_id, strategy_id, start_date, end_date)
        
        if not trades:
            return StrategyComparison(
                strategy_id=strategy_id,
                strategy_name=strategy_id,
                total_trades=0,
                win_rate=0.0,
                total_pnl=Decimal("0"),
                sharpe_ratio=0.0,
                max_drawdown_percent=0.0,
                profit_factor=0.0,
                avg_trade_duration=0.0,
            )
        
        # Calculate metrics
        wins = sum(1 for t in trades if t.outcome == TradeOutcome.WIN)
        total_pnl = sum(t.pnl for t in trades)
        
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = sum(t.pnl for t in trades if t.pnl < 0)
        
        profit_factor = float(gross_profit / abs(gross_loss)) if gross_loss != 0 else float("inf")
        
        # Calculate durations
        durations = [
            t.duration_minutes for t in trades
            if t.duration_minutes is not None
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        
        # Get Sharpe and drawdown
        sharpe_data = self.calculate_sharpe_ratio(user_id, strategy_id)
        drawdown_data = self.analyze_drawdowns(user_id, strategy_id)
        
        return StrategyComparison(
            strategy_id=strategy_id,
            strategy_name=strategy_id,
            total_trades=len(trades),
            win_rate=(wins / len(trades)) * 100,
            total_pnl=total_pnl,
            sharpe_ratio=sharpe_data.get("annualized_sharpe_ratio", 0.0),
            max_drawdown_percent=drawdown_data.get("max_drawdown_percent", 0.0),
            profit_factor=profit_factor,
            avg_trade_duration=avg_duration,
        )
    
    def _calculate_period_performance(
        self,
        user_id: str,
        strategy_id: str | None,
        start_date: datetime,
        end_date: datetime,
    ) -> PeriodPerformance:
        """Calculate performance for a specific period."""
        trades = self._get_closed_trades(user_id, strategy_id, start_date, end_date)
        
        perf = PeriodPerformance(
            period_start=start_date,
            period_end=end_date,
        )
        
        for trade in trades:
            perf.total_trades += 1
            perf.total_pnl += trade.pnl
            
            if trade.outcome == TradeOutcome.WIN:
                perf.winning_trades += 1
                perf.gross_profit += trade.pnl
            elif trade.outcome == TradeOutcome.LOSS:
                perf.losing_trades += 1
                perf.gross_loss += trade.pnl
            else:
                perf.break_even_trades += 1
        
        return perf


# Global evaluator instance
_evaluator: PracticeEvaluator | None = None


def get_practice_evaluator(db: Session) -> PracticeEvaluator:
    """Get or create the practice evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = PracticeEvaluator(db)
    return _evaluator
