"""
MiroFish Backtest - Historical backtesting of MiroFish signals.

Provides:
- Backtest MiroFish signals on historical data
- Compare different MiroFish configurations
- Optimize parameters
- Walk-forward analysis
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any
from enum import Enum

from sqlalchemy import Column, String, Float, DateTime, JSON, Integer, Boolean
from app.core.database import Base, get_db

from app.services.mirofish.mirofish_service import mirofish_predict, mirofish_deep_swarm
from app.services.mirofish.mirofish_fleet import DirectionalBias

logger = logging.getLogger(__name__)


# Database Models
class MiroFishBacktest(Base):
    """Database model for storing backtest results."""
    __tablename__ = "mirofish_backtests"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Backtest parameters
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    timeframe = Column(String(10), nullable=False)
    initial_capital = Column(Float, default=100000.0)
    
    # Results summary
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Performance metrics
    total_return = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    
    # Detailed results
    trades = Column(JSON, default=list)
    equity_curve = Column(JSON, default=list)
    monthly_returns = Column(JSON, default=dict)
    
    # Configuration
    config = Column(JSON, default=dict)
    metadata = Column(JSON, default=dict)


class MiroFishBacktestConfig(Base):
    """Database model for storing backtest configurations."""
    __tablename__ = "mirofish_backtest_configs"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Configuration parameters
    entry_threshold = Column(Float, default=0.6)  # Min confidence to enter
    exit_threshold = Column(Float, default=0.3)  # Max confidence to hold
    stop_loss_pct = Column(Float, default=0.05)  # Stop loss percentage
    take_profit_pct = Column(Float, default=0.10)  # Take profit percentage
    max_position_size = Column(Float, default=0.2)  # Max % of capital per trade
    max_holding_days = Column(Integer, default=5)
    
    # Signal configuration
    use_deep_swarm = Column(Boolean, default=False)
    timeframes = Column(JSON, default=list)
    lenses = Column(JSON, default=list)
    
    metadata = Column(JSON, default=dict)


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(Enum):
    """Trade status."""
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"
    TARGET = "target"
    EXPIRED = "expired"


@dataclass
class BacktestTrade:
    """Individual backtest trade."""
    id: str
    ticker: str
    entry_date: datetime
    entry_price: float
    direction: TradeDirection
    shares: float
    
    exit_date: datetime | None = None
    exit_price: float | None = None
    exit_status: TradeStatus | None = None
    
    pnl: float = 0.0
    pnl_pct: float = 0.0
    
    # Signal info
    entry_confidence: float = 0.0
    entry_bias: str = "NEUTRAL"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "direction": self.direction.value,
            "entry": {
                "date": self.entry_date.isoformat() if self.entry_date else None,
                "price": round(self.entry_price, 4),
                "confidence": round(self.entry_confidence, 4),
                "bias": self.entry_bias,
            },
            "exit": {
                "date": self.exit_date.isoformat() if self.exit_date else None,
                "price": round(self.exit_price, 4) if self.exit_price else None,
                "status": self.exit_status.value if self.exit_status else None,
            },
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 4),
            "is_winner": self.pnl > 0,
        }


@dataclass
class BacktestResult:
    """Complete backtest results."""
    id: str
    name: str
    ticker: str
    start_date: datetime
    end_date: datetime
    
    # Trades
    trades: list[BacktestTrade] = field(default_factory=list)
    
    # Performance
    initial_capital: float = 100000.0
    final_capital: float = 100000.0
    
    # Metrics
    total_return: float = 0.0
    total_return_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_trade_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Time series
    equity_curve: list[dict] = field(default_factory=list)
    daily_returns: list[float] = field(default_factory=list)
    
    # Configuration
    config: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ticker": self.ticker,
            "period": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
            },
            "capital": {
                "initial": round(self.initial_capital, 2),
                "final": round(self.final_capital, 2),
            },
            "performance": {
                "total_return": round(self.total_return, 2),
                "total_return_pct": round(self.total_return_pct, 4),
                "win_rate": round(self.win_rate, 4),
                "profit_factor": round(self.profit_factor, 4),
                "sharpe_ratio": round(self.sharpe_ratio, 4),
                "sortino_ratio": round(self.sortino_ratio, 4),
                "max_drawdown": round(self.max_drawdown, 2),
                "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            },
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "avg_pnl": round(self.avg_trade_pnl, 4),
                "avg_win": round(self.avg_win, 4),
                "avg_loss": round(self.avg_loss, 4),
                "largest_win": round(self.largest_win, 4),
                "largest_loss": round(self.largest_loss, 4),
            },
            "trade_list": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
            "config": self.config,
        }


class MiroFishBacktester:
    """
    Backtests MiroFish signals on historical data.
    
    Features:
    - Historical signal backtesting
    - Multiple configuration comparison
    - Parameter optimization
    - Walk-forward analysis
    """
    
    DEFAULT_CONFIG = {
        "entry_threshold": 0.6,
        "exit_threshold": 0.3,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10,
        "max_position_size": 0.2,
        "max_holding_days": 5,
        "use_deep_swarm": False,
        "timeframes": ["5m", "15m", "1h"],
        "lenses": ["trend", "risk"],
    }
    
    def __init__(self):
        self.config = self.DEFAULT_CONFIG.copy()
    
    async def run_backtest(
        self,
        ticker: str,
        historical_data: list[dict],
        config: dict | None = None,
        name: str | None = None,
    ) -> BacktestResult:
        """
        Run backtest on historical data.
        
        Args:
            ticker: Stock symbol
            historical_data: List of historical price data with dates
            config: Backtest configuration override
            name: Backtest name
            
        Returns:
            BacktestResult with full results
        """
        ticker = ticker.upper()
        backtest_config = {**self.config, **(config or {})}
        
        backtest_id = f"bt_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        if not historical_data:
            logger.warning(f"No historical data provided for {ticker}")
            return self._create_empty_result(backtest_id, name or f"Backtest_{ticker}", ticker)
        
        # Sort by date
        historical_data = sorted(historical_data, key=lambda x: x.get("date", ""))
        
        start_date = datetime.fromisoformat(historical_data[0].get("date"))
        end_date = datetime.fromisoformat(historical_data[-1].get("date"))
        
        # Run simulation
        capital = backtest_config.get("initial_capital", 100000.0)
        trades: list[BacktestTrade] = []
        equity_curve: list[dict] = []
        open_trade: BacktestTrade | None = None
        
        for i, bar in enumerate(historical_data):
            current_date = datetime.fromisoformat(bar.get("date"))
            current_price = bar.get("close", 0)
            
            # Record equity
            equity = capital
            if open_trade:
                # Mark to market
                if open_trade.direction == TradeDirection.LONG:
                    unrealized = (current_price - open_trade.entry_price) * open_trade.shares
                else:
                    unrealized = (open_trade.entry_price - current_price) * open_trade.shares
                equity += unrealized
            
            equity_curve.append({
                "date": current_date.isoformat(),
                "equity": round(equity, 2),
                "price": current_price,
            })
            
            # Check for exit if we have an open trade
            if open_trade:
                exit_result = self._check_exit(
                    open_trade, current_price, current_date, bar, i, historical_data, backtest_config
                )
                
                if exit_result:
                    # Close trade
                    open_trade.exit_date = current_date
                    open_trade.exit_price = current_price
                    open_trade.exit_status = exit_result["status"]
                    
                    # Calculate P&L
                    if open_trade.direction == TradeDirection.LONG:
                        open_trade.pnl = (current_price - open_trade.entry_price) * open_trade.shares
                    else:
                        open_trade.pnl = (open_trade.entry_price - current_price) * open_trade.shares
                    
                    open_trade.pnl_pct = open_trade.pnl / (open_trade.entry_price * open_trade.shares)
                    capital += open_trade.pnl
                    
                    trades.append(open_trade)
                    open_trade = None
            
            # Check for entry if no open trade
            elif i < len(historical_data) - 1:  # Don't enter on last bar
                signal = await self._get_signal_at_bar(ticker, bar, backtest_config)
                
                if signal and signal.get("confidence", 0) >= backtest_config["entry_threshold"]:
                    bias = signal.get("directional_bias", "NEUTRAL")
                    
                    if bias in ["BULLISH", "BEARISH"]:
                        direction = TradeDirection.LONG if bias == "BULLISH" else TradeDirection.SHORT
                        
                        # Calculate position size
                        position_value = capital * backtest_config["max_position_size"]
                        shares = position_value / current_price
                        
                        open_trade = BacktestTrade(
                            id=f"trade_{len(trades)}_{ticker}",
                            ticker=ticker,
                            entry_date=current_date,
                            entry_price=current_price,
                            direction=direction,
                            shares=shares,
                            entry_confidence=signal.get("confidence", 0),
                            entry_bias=bias,
                        )
        
        # Close any open trade at end
        if open_trade and historical_data:
            last_bar = historical_data[-1]
            final_price = last_bar.get("close", open_trade.entry_price)
            final_date = datetime.fromisoformat(last_bar.get("date"))
            
            open_trade.exit_date = final_date
            open_trade.exit_price = final_price
            open_trade.exit_status = TradeStatus.EXPIRED
            
            if open_trade.direction == TradeDirection.LONG:
                open_trade.pnl = (final_price - open_trade.entry_price) * open_trade.shares
            else:
                open_trade.pnl = (open_trade.entry_price - final_price) * open_trade.shares
            
            open_trade.pnl_pct = open_trade.pnl / (open_trade.entry_price * open_trade.shares)
            capital += open_trade.pnl
            trades.append(open_trade)
        
        # Calculate metrics
        result = self._calculate_metrics(
            backtest_id=backtest_id,
            name=name or f"Backtest_{ticker}",
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            initial_capital=backtest_config.get("initial_capital", 100000.0),
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve,
            config=backtest_config,
        )
        
        # Store in database
        await self._store_backtest(result)
        
        return result
    
    async def _get_signal_at_bar(
        self,
        ticker: str,
        bar: dict,
        config: dict,
    ) -> dict | None:
        """Get MiroFish signal for a specific bar."""
        try:
            if config.get("use_deep_swarm", False):
                result = await mirofish_deep_swarm({
                    "ticker": ticker,
                    "timeframes": config.get("timeframes", ["5m"]),
                    "lenses": config.get("lenses", ["trend"]),
                })
                return {
                    "directional_bias": result.get("overall_bias", "NEUTRAL"),
                    "confidence": result.get("overall_confidence", 0.5),
                }
            else:
                return await mirofish_predict({
                    "ticker": ticker,
                    "timeframe": config.get("timeframes", ["5m"])[0],
                })
        except Exception as e:
            logger.error(f"Error getting signal: {e}")
            return None
    
    def _check_exit(
        self,
        trade: BacktestTrade,
        current_price: float,
        current_date: datetime,
        bar: dict,
        bar_index: int,
        historical_data: list[dict],
        config: dict,
    ) -> dict | None:
        """Check if trade should be exited."""
        entry_price = trade.entry_price
        
        # Check stop loss
        if trade.direction == TradeDirection.LONG:
            stop_price = entry_price * (1 - config["stop_loss_pct"])
            if current_price <= stop_price:
                return {"status": TradeStatus.STOPPED, "reason": "stop_loss"}
            
            # Check take profit
            target_price = entry_price * (1 + config["take_profit_pct"])
            if current_price >= target_price:
                return {"status": TradeStatus.TARGET, "reason": "take_profit"}
        
        else:  # SHORT
            stop_price = entry_price * (1 + config["stop_loss_pct"])
            if current_price >= stop_price:
                return {"status": TradeStatus.STOPPED, "reason": "stop_loss"}
            
            # Check take profit
            target_price = entry_price * (1 - config["take_profit_pct"])
            if current_price <= target_price:
                return {"status": TradeStatus.TARGET, "reason": "take_profit"}
        
        # Check max holding days
        days_held = (current_date - trade.entry_date).days
        if days_held >= config["max_holding_days"]:
            return {"status": TradeStatus.EXPIRED, "reason": "max_hold_time"}
        
        return None
    
    def _calculate_metrics(
        self,
        backtest_id: str,
        name: str,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        final_capital: float,
        trades: list[BacktestTrade],
        equity_curve: list[dict],
        config: dict,
    ) -> BacktestResult:
        """Calculate all backtest metrics."""
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        losing_trades = sum(1 for t in trades if t.pnl <= 0)
        
        total_return = final_capital - initial_capital
        total_return_pct = total_return / initial_capital if initial_capital > 0 else 0
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Calculate P&L stats
        pnls = [t.pnl for t in trades]
        avg_trade_pnl = sum(pnls) / len(pnls) if pnls else 0
        
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl <= 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        # Profit factor
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Calculate max drawdown
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        peak = initial_capital
        
        for point in equity_curve:
            equity = point["equity"]
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            drawdown_pct = drawdown / peak if peak > 0 else 0
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_pct = drawdown_pct
        
        # Calculate Sharpe ratio (simplified)
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
        
        if len(daily_returns) > 1:
            mean_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = variance ** 0.5
            sharpe_ratio = (mean_return / std_dev) * (252 ** 0.5) if std_dev > 0 else 0  # Annualized
            
            # Sortino ratio (downside deviation only)
            downside_returns = [r for r in daily_returns if r < 0]
            downside_std = (sum(r ** 2 for r in downside_returns) / len(downside_returns)) ** 0.5 if downside_returns else 0
            sortino_ratio = (mean_return / downside_std) * (252 ** 0.5) if downside_std > 0 else 0
        else:
            sharpe_ratio = 0
            sortino_ratio = 0
        
        return BacktestResult(
            id=backtest_id,
            name=name,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            initial_capital=initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_trade_pnl=avg_trade_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            config=config,
        )
    
    def _create_empty_result(self, backtest_id: str, name: str, ticker: str) -> BacktestResult:
        """Create empty result for no data case."""
        now = datetime.now(timezone.utc)
        return BacktestResult(
            id=backtest_id,
            name=name,
            ticker=ticker,
            start_date=now,
            end_date=now,
        )
    
    async def optimize_parameters(
        self,
        ticker: str,
        historical_data: list[dict],
        param_grid: dict | None = None,
    ) -> dict:
        """
        Optimize backtest parameters using grid search.
        
        Args:
            ticker: Stock symbol
            historical_data: Historical price data
            param_grid: Dictionary of parameter ranges to test
            
        Returns:
            Dictionary with best parameters and comparison results
        """
        default_grid = {
            "entry_threshold": [0.5, 0.6, 0.7],
            "stop_loss_pct": [0.03, 0.05, 0.07],
            "take_profit_pct": [0.08, 0.10, 0.15],
            "max_holding_days": [3, 5, 7],
        }
        
        grid = param_grid or default_grid
        results = []
        
        # Generate all combinations
        from itertools import product
        
        keys = list(grid.keys())
        values = list(grid.values())
        
        for combination in product(*values):
            config = dict(zip(keys, combination))
            config["initial_capital"] = 100000.0
            
            result = await self.run_backtest(
                ticker=ticker,
                historical_data=historical_data,
                config=config,
                name=f"Opt_{'_'.join(f'{k}={v}' for k, v in config.items())}",
            )
            
            results.append({
                "config": config,
                "sharpe_ratio": result.sharpe_ratio,
                "total_return_pct": result.total_return_pct,
                "win_rate": result.win_rate,
                "max_drawdown_pct": result.max_drawdown_pct,
                "profit_factor": result.profit_factor,
                "score": result.sharpe_ratio * result.win_rate * (1 + result.total_return_pct),
            })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "ticker": ticker,
            "total_combinations": len(results),
            "best_config": results[0]["config"] if results else {},
            "best_score": results[0]["score"] if results else 0,
            "top_results": results[:10],
        }
    
    async def walk_forward_analysis(
        self,
        ticker: str,
        historical_data: list[dict],
        train_size: int = 60,
        test_size: int = 20,
        config: dict | None = None,
    ) -> dict:
        """
        Perform walk-forward analysis.
        
        Args:
            ticker: Stock symbol
            historical_data: Historical price data
            train_size: Number of bars for training/optimization
            test_size: Number of bars for testing
            config: Base configuration
            
        Returns:
            Dictionary with walk-forward results
        """
        if len(historical_data) < train_size + test_size:
            return {"error": "Insufficient data for walk-forward analysis"}
        
        periods = []
        start_idx = 0
        
        while start_idx + train_size + test_size <= len(historical_data):
            train_data = historical_data[start_idx:start_idx + train_size]
            test_data = historical_data[start_idx + train_size:start_idx + train_size + test_size]
            
            # Optimize on training data
            opt_result = await self.optimize_parameters(ticker, train_data)
            best_config = opt_result.get("best_config", {})
            
            # Test on out-of-sample data
            test_result = await self.run_backtest(
                ticker=ticker,
                historical_data=test_data,
                config={**self.config, **best_config, **(config or {})},
                name=f"WF_Test_{start_idx}",
            )
            
            periods.append({
                "period": len(periods) + 1,
                "train_start": train_data[0].get("date"),
                "train_end": train_data[-1].get("date"),
                "test_start": test_data[0].get("date"),
                "test_end": test_data[-1].get("date"),
                "optimized_config": best_config,
                "test_results": {
                    "return_pct": test_result.total_return_pct,
                    "sharpe_ratio": test_result.sharpe_ratio,
                    "win_rate": test_result.win_rate,
                    "max_drawdown_pct": test_result.max_drawdown_pct,
                },
            })
            
            start_idx += test_size
        
        # Aggregate results
        if periods:
            avg_return = sum(p["test_results"]["return_pct"] for p in periods) / len(periods)
            avg_sharpe = sum(p["test_results"]["sharpe_ratio"] for p in periods) / len(periods)
            avg_win_rate = sum(p["test_results"]["win_rate"] for p in periods) / len(periods)
        else:
            avg_return = avg_sharpe = avg_win_rate = 0
        
        return {
            "ticker": ticker,
            "periods": periods,
            "summary": {
                "num_periods": len(periods),
                "avg_return_pct": round(avg_return, 4),
                "avg_sharpe_ratio": round(avg_sharpe, 4),
                "avg_win_rate": round(avg_win_rate, 4),
            },
        }
    
    async def _store_backtest(self, result: BacktestResult) -> None:
        """Store backtest result in database."""
        try:
            db = next(get_db())
            
            record = MiroFishBacktest(
                id=result.id,
                name=result.name,
                ticker=result.ticker,
                start_date=result.start_date,
                end_date=result.end_date,
                timeframe=result.config.get("timeframes", ["5m"])[0] if result.config.get("timeframes") else "5m",
                initial_capital=result.initial_capital,
                total_trades=result.total_trades,
                winning_trades=result.winning_trades,
                losing_trades=result.losing_trades,
                win_rate=result.win_rate,
                total_return=result.total_return,
                total_return_pct=result.total_return_pct,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown,
                max_drawdown_pct=result.max_drawdown_pct,
                trades=[t.to_dict() for t in result.trades],
                equity_curve=result.equity_curve,
                config=result.config,
            )
            
            db.merge(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store backtest: {e}")


# Singleton instance
_backtester: MiroFishBacktester | None = None


def get_backtester() -> MiroFishBacktester:
    """Get or create the singleton backtester instance."""
    global _backtester
    if _backtester is None:
        _backtester = MiroFishBacktester()
    return _backtester


async def run_backtest(
    ticker: str,
    historical_data: list[dict],
    config: dict | None = None,
    name: str | None = None,
) -> dict:
    """Convenience function to run a backtest."""
    backtester = get_backtester()
    result = await backtester.run_backtest(
        ticker=ticker,
        historical_data=historical_data,
        config=config,
        name=name,
    )
    return result.to_dict()


async def optimize_parameters(
    ticker: str,
    historical_data: list[dict],
    param_grid: dict | None = None,
) -> dict:
    """Convenience function for parameter optimization."""
    backtester = get_backtester()
    return await backtester.optimize_parameters(ticker, historical_data, param_grid)


async def walk_forward_analysis(
    ticker: str,
    historical_data: list[dict],
    train_size: int = 60,
    test_size: int = 20,
    config: dict | None = None,
) -> dict:
    """Convenience function for walk-forward analysis."""
    backtester = get_backtester()
    return await backtester.walk_forward_analysis(
        ticker=ticker,
        historical_data=historical_data,
        train_size=train_size,
        test_size=test_size,
        config=config,
    )
