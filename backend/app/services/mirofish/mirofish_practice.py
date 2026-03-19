"""
MiroFish Practice - Paper trading practice mode.

Provides:
- Simulate trades based on MiroFish signals
- Track hypothetical P&L
- Compare different MiroFish configurations
- Learning from outcomes
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from app.services.mirofish.mirofish_fleet import get_fleet, DirectionalBias
from app.services.mirofish.mirofish_ensemble import (
    get_ensemble,
    Action,
    SignalSource,
    create_agent_signal,
)

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """Status of a practice trade."""
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TradeDirection(Enum):
    """Direction of a trade."""
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(Enum):
    """Reason for trade exit."""
    TARGET_HIT = "target_hit"
    STOP_LOSS = "stop_loss"
    SIGNAL_REVERSAL = "signal_reversal"
    TIME_EXPIRED = "time_expired"
    MANUAL = "manual"
    MAX_HOLD_TIME = "max_hold_time"


@dataclass
class PracticeTrade:
    """A practice/paper trade."""
    trade_id: str
    ticker: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    quantity: int
    
    # Exit details
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: ExitReason | None = None
    
    # P&L
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    return_pct: float = 0.0
    
    # Configuration used
    config_name: str = "default"
    mirofish_signal: dict | None = None
    
    # Status
    status: TradeStatus = TradeStatus.OPEN
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "ticker": self.ticker,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "quantity": self.quantity,
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "gross_pnl": self.gross_pnl,
            "net_pnl": self.net_pnl,
            "return_pct": self.return_pct,
            "config_name": self.config_name,
            "mirofish_signal": self.mirofish_signal,
            "status": self.status.value,
            "metadata": self.metadata,
            "tags": self.tags,
        }


@dataclass
class PracticeSession:
    """A practice trading session."""
    session_id: str
    name: str
    config_name: str
    started_at: datetime
    
    # Trades
    trades: list[PracticeTrade] = field(default_factory=list)
    
    # Settings
    initial_capital: float = 100000.0
    max_position_size: float = 10000.0
    max_concurrent_trades: int = 5
    
    # Status
    ended_at: datetime | None = None
    status: str = "active"
    
    # Metadata
    description: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def current_capital(self) -> float:
        """Calculate current capital including open positions."""
        capital = self.initial_capital
        for trade in self.trades:
            if trade.status == TradeStatus.CLOSED:
                capital += trade.net_pnl
            elif trade.status == TradeStatus.OPEN:
                # Mark to market would go here with live prices
                pass
        return capital

    @property
    def total_return_pct(self) -> float:
        """Calculate total return percentage."""
        if self.initial_capital == 0:
            return 0.0
        return ((self.current_capital - self.initial_capital) / self.initial_capital) * 100

    @property
    def closed_trades(self) -> list[PracticeTrade]:
        """Get all closed trades."""
        return [t for t in self.trades if t.status == TradeStatus.CLOSED]

    @property
    def open_trades(self) -> list[PracticeTrade]:
        """Get all open trades."""
        return [t for t in self.trades if t.status == TradeStatus.OPEN]

    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        closed = self.closed_trades
        if not closed:
            return 0.0
        winners = sum(1 for t in closed if t.net_pnl > 0)
        return winners / len(closed)

    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        closed = self.closed_trades
        gross_profit = sum(t.net_pnl for t in closed if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in closed if t.net_pnl < 0))
        if gross_loss == 0:
            return gross_profit if gross_profit > 0 else 1.0
        return gross_profit / gross_loss

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "config_name": self.config_name,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "total_return_pct": self.total_return_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": len(self.trades),
            "closed_trades": len(self.closed_trades),
            "open_trades": len(self.open_trades),
            "description": self.description,
            "tags": self.tags,
        }


@dataclass
class MiroFishConfig:
    """Configuration for MiroFish signal generation."""
    name: str
    description: str
    
    # Analysis parameters
    timeframes: list[str] = field(default_factory=lambda: ["5m", "15m", "1h"])
    lenses: list[str] = field(default_factory=lambda: ["technical", "trend"])
    aggregation_method: str = "weighted"
    
    # Signal thresholds
    min_confidence: float = 0.6
    min_alignment_score: float = 0.5
    
    # Entry rules
    entry_on_bias: DirectionalBias = DirectionalBias.BULLISH
    require_consensus: bool = False
    
    # Exit rules
    take_profit_pct: float = 0.04  # 4%
    stop_loss_pct: float = 0.02    # 2%
    max_hold_time_hours: int = 24
    exit_on_signal_reversal: bool = True
    
    # Risk management
    position_size_pct: float = 0.1  # 10% of capital per trade
    max_positions: int = 5
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "timeframes": self.timeframes,
            "lenses": self.lenses,
            "aggregation_method": self.aggregation_method,
            "min_confidence": self.min_confidence,
            "min_alignment_score": self.min_alignment_score,
            "entry_on_bias": self.entry_on_bias.value,
            "require_consensus": self.require_consensus,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "max_hold_time_hours": self.max_hold_time_hours,
            "exit_on_signal_reversal": self.exit_on_signal_reversal,
            "position_size_pct": self.position_size_pct,
            "max_positions": self.max_positions,
        }


# Default configurations
DEFAULT_CONFIGS = {
    "conservative": MiroFishConfig(
        name="conservative",
        description="Conservative approach with high confidence requirements",
        timeframes=["15m", "1h", "1d"],
        lenses=["technical", "fundamental", "risk"],
        min_confidence=0.75,
        min_alignment_score=0.7,
        take_profit_pct=0.03,
        stop_loss_pct=0.015,
        position_size_pct=0.05,
    ),
    "aggressive": MiroFishConfig(
        name="aggressive",
        description="Aggressive approach with lower thresholds",
        timeframes=["1m", "5m", "15m", "1h"],
        lenses=["technical", "momentum", "sentiment"],
        min_confidence=0.5,
        min_alignment_score=0.4,
        take_profit_pct=0.06,
        stop_loss_pct=0.03,
        position_size_pct=0.15,
        max_positions=8,
    ),
    "balanced": MiroFishConfig(
        name="balanced",
        description="Balanced approach with moderate settings",
        timeframes=["5m", "15m", "1h", "1d"],
        lenses=["technical", "sentiment", "trend", "risk"],
        min_confidence=0.6,
        min_alignment_score=0.5,
        take_profit_pct=0.04,
        stop_loss_pct=0.02,
        position_size_pct=0.1,
        max_positions=5,
    ),
    "swing": MiroFishConfig(
        name="swing",
        description="Swing trading with longer hold times",
        timeframes=["1h", "4h", "1d"],
        lenses=["technical", "fundamental", "catalyst"],
        min_confidence=0.65,
        min_alignment_score=0.6,
        take_profit_pct=0.08,
        stop_loss_pct=0.04,
        max_hold_time_hours=72,
        position_size_pct=0.12,
        max_positions=3,
    ),
}


class MiroFishPractice:
    """
    Paper trading practice mode for MiroFish signals.
    
    Features:
    - Simulate trades based on MiroFish signals
    - Track hypothetical P&L
    - Compare different MiroFish configurations
    - Learning from outcomes
    """

    def __init__(self):
        self.sessions: dict[str, PracticeSession] = {}
        self.configs: dict[str, MiroFishConfig] = DEFAULT_CONFIGS.copy()
        self.fleet = get_fleet()
        self.ensemble = get_ensemble()

    def create_session(
        self,
        name: str,
        config_name: str = "balanced",
        initial_capital: float = 100000.0,
        description: str = "",
        tags: list[str] | None = None,
    ) -> PracticeSession:
        """
        Create a new practice trading session.
        
        Args:
            name: Session name
            config_name: Configuration to use (conservative, aggressive, balanced, swing)
            initial_capital: Starting capital
            description: Session description
            tags: Optional tags
            
        Returns:
            New PracticeSession
        """
        session_id = str(uuid.uuid4())[:8]
        
        session = PracticeSession(
            session_id=session_id,
            name=name,
            config_name=config_name,
            started_at=datetime.now(timezone.utc),
            initial_capital=initial_capital,
            description=description,
            tags=tags or [],
        )
        
        self.sessions[session_id] = session
        logger.info(f"Created practice session {session_id}: {name}")
        
        return session

    async def evaluate_entry(
        self,
        session_id: str,
        ticker: str,
        current_price: float,
    ) -> dict:
        """
        Evaluate whether to enter a trade based on MiroFish signals.
        
        Args:
            session_id: Practice session ID
            ticker: Stock symbol
            current_price: Current market price
            
        Returns:
            Entry decision with signal details
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found", "should_enter": False}

        config = self.configs.get(session.config_name, self.configs["balanced"])

        # Check position limits
        open_positions = len(session.open_trades)
        if open_positions >= config.max_positions:
            return {
                "should_enter": False,
                "reason": f"Max positions reached ({config.max_positions})",
            }

        # Get MiroFish analysis
        fleet_result = await self.fleet.analyze(
            ticker=ticker,
            timeframes=config.timeframes,
            lenses=config.lenses,
            aggregation_method=config.aggregation_method,
        )

        # Check entry conditions
        entry_conditions = self._check_entry_conditions(fleet_result, config)

        if entry_conditions["should_enter"]:
            # Calculate position size
            position_value = session.current_capital * config.position_size_pct
            quantity = int(position_value / current_price)

            if quantity < 1:
                return {
                    "should_enter": False,
                    "reason": "Insufficient capital for minimum position",
                    "analysis": fleet_result.to_dict(),
                }

            return {
                "should_enter": True,
                "direction": TradeDirection.LONG if fleet_result.aggregated_bias == DirectionalBias.BULLISH else TradeDirection.SHORT,
                "quantity": quantity,
                "confidence": fleet_result.aggregated_confidence,
                "analysis": fleet_result.to_dict(),
                "conditions_met": entry_conditions["conditions_met"],
            }

        return {
            "should_enter": False,
            "reason": entry_conditions["reason"],
            "analysis": fleet_result.to_dict(),
            "conditions_met": entry_conditions["conditions_met"],
        }

    async def enter_trade(
        self,
        session_id: str,
        ticker: str,
        direction: TradeDirection,
        entry_price: float,
        quantity: int,
        mirofish_signal: dict | None = None,
    ) -> PracticeTrade | None:
        """
        Enter a new practice trade.
        
        Args:
            session_id: Practice session ID
            ticker: Stock symbol
            direction: LONG or SHORT
            entry_price: Entry price
            quantity: Number of shares
            mirofish_signal: Signal that triggered the trade
            
        Returns:
            New PracticeTrade or None if failed
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        config = self.configs.get(session.config_name, self.configs["balanced"])

        # Check position limits
        if len(session.open_trades) >= config.max_positions:
            logger.warning(f"Cannot enter trade: max positions reached for session {session_id}")
            return None

        trade = PracticeTrade(
            trade_id=str(uuid.uuid4())[:8],
            ticker=ticker.upper(),
            direction=direction,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc),
            quantity=quantity,
            config_name=session.config_name,
            mirofish_signal=mirofish_signal,
            tags=session.tags.copy(),
        )

        session.trades.append(trade)
        logger.info(f"Entered {direction.value} trade for {ticker} in session {session_id}")

        return trade

    async def evaluate_exit(
        self,
        session_id: str,
        trade_id: str,
        current_price: float,
    ) -> dict:
        """
        Evaluate whether to exit an open trade.
        
        Args:
            session_id: Practice session ID
            trade_id: Trade ID
            current_price: Current market price
            
        Returns:
            Exit decision with reasons
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found", "should_exit": False}

        trade = next((t for t in session.open_trades if t.trade_id == trade_id), None)
        if not trade:
            return {"error": "Trade not found or already closed", "should_exit": False}

        config = self.configs.get(trade.config_name, self.configs["balanced"])

        exit_checks = self._check_exit_conditions(trade, current_price, config)

        return {
            "should_exit": exit_checks["should_exit"],
            "reason": exit_checks["reason"],
            "exit_reason": exit_checks["exit_reason"].value if exit_checks["exit_reason"] else None,
            "unrealized_pnl": exit_checks["unrealized_pnl"],
            "unrealized_pct": exit_checks["unrealized_pct"],
        }

    async def exit_trade(
        self,
        session_id: str,
        trade_id: str,
        exit_price: float,
        exit_reason: ExitReason,
    ) -> PracticeTrade | None:
        """
        Exit an open practice trade.
        
        Args:
            session_id: Practice session ID
            trade_id: Trade ID
            exit_price: Exit price
            exit_reason: Reason for exit
            
        Returns:
            Updated PracticeTrade or None if failed
        """
        session = self.sessions.get(session_id)
        if not session:
            return None

        trade = next((t for t in session.open_trades if t.trade_id == trade_id), None)
        if not trade:
            return None

        # Calculate P&L
        if trade.direction == TradeDirection.LONG:
            gross_pnl = (exit_price - trade.entry_price) * trade.quantity
        else:
            gross_pnl = (trade.entry_price - exit_price) * trade.quantity

        # Assume small commission/slippage
        commission = abs(gross_pnl) * 0.001  # 0.1%
        net_pnl = gross_pnl - commission

        return_pct = (net_pnl / (trade.entry_price * trade.quantity)) * 100

        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_reason = exit_reason
        trade.gross_pnl = gross_pnl
        trade.net_pnl = net_pnl
        trade.return_pct = return_pct
        trade.status = TradeStatus.CLOSED

        # Record outcome for ensemble learning
        action = Action.LONG if trade.direction == TradeDirection.LONG else Action.SHORT
        self.ensemble.record_outcome(
            source=SignalSource.MIROFISH,
            ticker=trade.ticker,
            predicted_action=action,
            actual_pnl=net_pnl,
        )

        logger.info(f"Exited trade {trade_id} for {trade.ticker}: P&L ${net_pnl:.2f}")

        return trade

    def get_session_performance(self, session_id: str) -> dict:
        """Get detailed performance metrics for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        closed = session.closed_trades
        
        if not closed:
            return {
                "session": session.to_dict(),
                "trades": [],
                "metrics": {
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "avg_return": 0.0,
                    "max_drawdown": 0.0,
                },
            }

        returns = [t.return_pct for t in closed]
        winning_trades = [t for t in closed if t.net_pnl > 0]
        losing_trades = [t for t in closed if t.net_pnl <= 0]

        # Calculate max drawdown
        cumulative = []
        running_total = 0
        for trade in closed:
            running_total += trade.return_pct
            cumulative.append(running_total)

        max_drawdown = 0.0
        peak = 0.0
        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        metrics = {
            "total_trades": len(closed),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": session.win_rate,
            "profit_factor": session.profit_factor,
            "avg_return": sum(returns) / len(returns),
            "avg_win": sum(t.return_pct for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            "avg_loss": sum(t.return_pct for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            "max_return": max(returns),
            "min_return": min(returns),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": self._calculate_sharpe(returns),
        }

        return {
            "session": session.to_dict(),
            "trades": [t.to_dict() for t in closed],
            "metrics": metrics,
        }

    def compare_configs(self, results: dict[str, dict]) -> dict:
        """
        Compare performance across different configurations.
        
        Args:
            results: Dict of config_name -> performance dict
            
        Returns:
            Comparison analysis
        """
        comparison = {
            "configs_compared": list(results.keys()),
            "rankings": {},
            "best_by_metric": {},
        }

        metrics_to_compare = [
            "total_return_pct",
            "win_rate",
            "profit_factor",
            "sharpe_ratio",
        ]

        for metric in metrics_to_compare:
            values = []
            for config_name, result in results.items():
                if "metrics" in result and metric in result["metrics"]:
                    values.append((config_name, result["metrics"][metric]))
                elif metric in result.get("session", {}):
                    values.append((config_name, result["session"][metric]))

            if values:
                best = max(values, key=lambda x: x[1])
                comparison["best_by_metric"][metric] = {
                    "config": best[0],
                    "value": best[1],
                }

        # Overall ranking by total return
        rankings = []
        for config_name, result in results.items():
            total_return = result.get("session", {}).get("total_return_pct", 0)
            rankings.append((config_name, total_return))

        rankings.sort(key=lambda x: x[1], reverse=True)
        comparison["rankings"] = {
            "by_total_return": [
                {"rank": i+1, "config": name, "return_pct": ret}
                for i, (name, ret) in enumerate(rankings)
            ],
        }

        return comparison

    def _check_entry_conditions(
        self,
        fleet_result,
        config: MiroFishConfig,
    ) -> dict:
        """Check if entry conditions are met."""
        conditions_met = []
        conditions_failed = []

        # Check confidence
        if fleet_result.aggregated_confidence >= config.min_confidence:
            conditions_met.append(f"confidence >= {config.min_confidence}")
        else:
            conditions_failed.append(f"confidence < {config.min_confidence}")

        # Check alignment
        if fleet_result.alignment_score >= config.min_alignment_score:
            conditions_met.append(f"alignment >= {config.min_alignment_score}")
        else:
            conditions_failed.append(f"alignment < {config.min_alignment_score}")

        # Check bias
        if fleet_result.aggregated_bias == config.entry_on_bias:
            conditions_met.append(f"bias is {config.entry_on_bias.value}")
        else:
            conditions_failed.append(f"bias is {fleet_result.aggregated_bias.value}, expected {config.entry_on_bias.value}")

        should_enter = len(conditions_failed) == 0

        return {
            "should_enter": should_enter,
            "conditions_met": conditions_met,
            "conditions_failed": conditions_failed,
            "reason": "; ".join(conditions_failed) if conditions_failed else "All conditions met",
        }

    def _check_exit_conditions(
        self,
        trade: PracticeTrade,
        current_price: float,
        config: MiroFishConfig,
    ) -> dict:
        """Check if exit conditions are met."""
        # Calculate unrealized P&L
        if trade.direction == TradeDirection.LONG:
            unrealized_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
        else:
            unrealized_pct = ((trade.entry_price - current_price) / trade.entry_price) * 100

        unrealized_pnl = (unrealized_pct / 100) * trade.entry_price * trade.quantity

        # Check take profit
        if unrealized_pct >= config.take_profit_pct * 100:
            return {
                "should_exit": True,
                "reason": f"Take profit hit ({unrealized_pct:.2f}%)",
                "exit_reason": ExitReason.TARGET_HIT,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pct": unrealized_pct,
            }

        # Check stop loss
        if unrealized_pct <= -config.stop_loss_pct * 100:
            return {
                "should_exit": True,
                "reason": f"Stop loss hit ({unrealized_pct:.2f}%)",
                "exit_reason": ExitReason.STOP_LOSS,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pct": unrealized_pct,
            }

        # Check max hold time
        hold_time = datetime.now(timezone.utc) - trade.entry_time
        if hold_time > timedelta(hours=config.max_hold_time_hours):
            return {
                "should_exit": True,
                "reason": f"Max hold time exceeded ({hold_time.total_seconds() / 3600:.1f}h)",
                "exit_reason": ExitReason.MAX_HOLD_TIME,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pct": unrealized_pct,
            }

        return {
            "should_exit": False,
            "reason": "Hold",
            "exit_reason": None,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pct": unrealized_pct,
        }

    def _calculate_sharpe(self, returns: list[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio for a series of returns."""
        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0.0

        return (avg_return - risk_free_rate) / std_dev


# Singleton instance
_practice: MiroFishPractice | None = None


def get_practice() -> MiroFishPractice:
    """Get or create the singleton practice instance."""
    global _practice
    if _practice is None:
        _practice = MiroFishPractice()
    return _practice


# Convenience functions
async def create_practice_session(
    name: str,
    config_name: str = "balanced",
    initial_capital: float = 100000.0,
) -> dict:
    """Create a new practice session."""
    practice = get_practice()
    session = practice.create_session(name, config_name, initial_capital)
    return session.to_dict()


async def evaluate_trade_entry(
    session_id: str,
    ticker: str,
    current_price: float,
) -> dict:
    """Evaluate entry for a ticker."""
    practice = get_practice()
    return await practice.evaluate_entry(session_id, ticker, current_price)


async def simulate_trade(
    session_id: str,
    ticker: str,
    direction: str,
    entry_price: float,
    quantity: int,
    signal: dict | None = None,
) -> dict:
    """Simulate entering a trade."""
    practice = get_practice()
    trade = await practice.enter_trade(
        session_id=session_id,
        ticker=ticker,
        direction=TradeDirection(direction.upper()),
        entry_price=entry_price,
        quantity=quantity,
        mirofish_signal=signal,
    )
    return trade.to_dict() if trade else {"error": "Failed to enter trade"}


async def close_trade(
    session_id: str,
    trade_id: str,
    exit_price: float,
    exit_reason: str,
) -> dict:
    """Close a practice trade."""
    practice = get_practice()
    trade = await practice.exit_trade(
        session_id=session_id,
        trade_id=trade_id,
        exit_price=exit_price,
        exit_reason=ExitReason(exit_reason.lower()),
    )
    return trade.to_dict() if trade else {"error": "Failed to exit trade"}


def get_session_results(session_id: str) -> dict:
    """Get results for a session."""
    practice = get_practice()
    return practice.get_session_performance(session_id)


def get_available_configs() -> dict:
    """Get available configurations."""
    practice = get_practice()
    return {name: config.to_dict() for name, config in practice.configs.items()}
