"""
Execution Simulation Agent

Paper trades approved setups.
Models fills, slippage, and realistic execution behavior.
Records complete trade lifecycle.

Outputs:
- Simulated fills
- Trade logs
- PnL tracking
- Execution quality metrics
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
import random

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class TradeStatus(Enum):
    """Status of a simulated trade."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExitReason(Enum):
    """Reason for trade exit."""
    TARGET_HIT = "target_hit"
    STOP_HIT = "stop_hit"
    TIME_STOP = "time_stop"
    MANUAL = "manual"
    SIGNAL_REVERSAL = "signal_reversal"


@dataclass
class SimulatedFill:
    """A simulated order fill."""
    fill_id: str
    order_id: str
    timestamp: datetime
    price: float
    size: float
    direction: str
    slippage: float
    commission: float
    fill_quality: str  # good, fair, poor


@dataclass
class SimulatedTrade:
    """A complete simulated trade."""
    trade_id: str
    proposal_id: str
    ticker: str
    
    # Entry
    entry_time: datetime
    entry_price: float
    entry_fill: Optional[SimulatedFill]
    position_size: float
    direction: str
    
    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_fill: Optional[SimulatedFill] = None
    exit_reason: Optional[ExitReason] = None
    
    # Targets
    stop_loss: float = 0
    take_profit: float = 0
    time_stop_hours: float = 72
    
    # PnL
    gross_pnl: float = 0
    net_pnl: float = 0
    return_pct: float = 0
    
    # Status
    status: TradeStatus = TradeStatus.PENDING
    
    # Lifecycle
    created_at: datetime = field(default_factory=datetime.utcnow)
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Execution quality
    entry_slippage: float = 0
    exit_slippage: float = 0
    total_commission: float = 0
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ExecutionMetrics:
    """Execution quality metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    total_gross_pnl: float = 0
    total_net_pnl: float = 0
    
    avg_entry_slippage: float = 0
    avg_exit_slippage: float = 0
    avg_commission: float = 0
    
    fill_rate: float = 0
    avg_fill_time_ms: float = 0
    
    # Quality distribution
    good_fills: int = 0
    fair_fills: int = 0
    poor_fills: int = 0


class ExecutionSimulationAgent(BaseAgent):
    """
    Agent for simulating trade execution with realistic market behavior.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("execution_simulation", message_bus, config)
        
        # Simulation parameters
        self.base_slippage_pct = config.get("base_slippage", 0.0005) if config else 0.0005  # 5 bps
        self.volatility_slippage_factor = config.get("vol_slippage_factor", 2.0) if config else 2.0
        self.commission_per_trade = config.get("commission", 1.0) if config else 1.0  # $1 per trade
        self.spread_pct = config.get("spread_pct", 0.0002) if config else 0.0002  # 2 bps
        self.fill_probability = config.get("fill_probability", 0.98) if config else 0.98
        
        # State
        self._active_trades: Dict[str, SimulatedTrade] = {}
        self._trade_history: List[SimulatedTrade] = []
        self._fills: List[SimulatedFill] = []
        self._metrics = ExecutionMetrics()
        
        # Market data cache
        self._price_cache: Dict[str, List[Dict]] = {}
        
        # Register handlers
        self.register_handler(MessageType.TRADE_APPROVED, self._handle_trade_approved)
        self.register_handler(MessageType.PRICE_ACTION_ALERT, self._handle_price_update)
        
    async def on_start(self):
        """Start trade monitoring loop."""
        asyncio.create_task(self._trade_monitor_loop())
        
    async def _trade_monitor_loop(self):
        """Monitor active trades for exits."""
        while self._running and self.state.value == "RUNNING":
            try:
                for trade in list(self._active_trades.values()):
                    if trade.status == TradeStatus.OPEN:
                        await self._check_trade_exit(trade)
                    elif trade.status == TradeStatus.PENDING:
                        await self._attempt_entry(trade)

                await asyncio.sleep(1)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Monitor loop error: {e}")
                await asyncio.sleep(5)
                
    async def _handle_trade_approved(self, message: AgentMessage):
        """Handle approved trade."""
        payload = message.payload
        proposal_id = payload.get("proposal_id")
        
        if proposal_id:
            await self._create_simulated_trade(payload)
            
    async def _handle_price_update(self, message: AgentMessage):
        """Handle price updates."""
        payload = message.payload
        ticker = payload.get("ticker")
        
        if ticker:
            if ticker not in self._price_cache:
                self._price_cache[ticker] = []
            self._price_cache[ticker].append({
                "timestamp": datetime.utcnow(),
                **payload
            })
            
            # Keep last 1000 prices
            if len(self._price_cache[ticker]) > 1000:
                self._price_cache[ticker] = self._price_cache[ticker][-1000:]
                
    async def _create_simulated_trade(self, approval: Dict[str, Any]) -> SimulatedTrade:
        """Create a new simulated trade from approval."""
        
        trade_id = f"sim_{approval.get('proposal_id', 'unknown')}"
        ticker = approval.get("ticker", "unknown")
        
        trade = SimulatedTrade(
            trade_id=trade_id,
            proposal_id=approval.get("proposal_id", ""),
            ticker=ticker,
            entry_time=datetime.utcnow(),
            entry_price=approval.get("entry_price", 0),
            entry_fill=None,
            position_size=approval.get("recommended_position_size", 0),
            direction=approval.get("direction", "long"),
            stop_loss=approval.get("stop_loss", 0),
            take_profit=approval.get("take_profit", 0),
            status=TradeStatus.PENDING,
        )
        
        self._active_trades[trade_id] = trade
        
        # Attempt immediate entry
        await self._attempt_entry(trade)
        
        return trade
        
    async def _attempt_entry(self, trade: SimulatedTrade):
        """Attempt to fill entry order."""
        
        # Simulate fill probability
        if random.random() > self.fill_probability:
            trade.notes.append(f"Entry fill failed at {datetime.utcnow()}")
            return
            
        # Calculate slippage
        slippage = self._calculate_slippage(trade.ticker, trade.direction, "entry")
        
        if trade.direction == "long":
            fill_price = trade.entry_price * (1 + slippage)
        else:
            fill_price = trade.entry_price * (1 - slippage)
            
        # Create fill
        fill = SimulatedFill(
            fill_id=f"fill_{trade.trade_id}_entry",
            order_id=trade.trade_id,
            timestamp=datetime.utcnow(),
            price=fill_price,
            size=trade.position_size,
            direction=trade.direction,
            slippage=slippage,
            commission=self.commission_per_trade,
            fill_quality=self._classify_fill_quality(slippage),
        )
        
        trade.entry_fill = fill
        trade.entry_price = fill_price
        trade.entry_slippage = slippage
        trade.total_commission += self.commission_per_trade
        trade.status = TradeStatus.OPEN
        trade.opened_at = datetime.utcnow()
        
        self._fills.append(fill)
        
        # Update metrics
        self._metrics.total_trades += 1
        self._metrics.avg_entry_slippage = (
            (self._metrics.avg_entry_slippage * (self._metrics.total_trades - 1) + slippage)
            / self._metrics.total_trades
        )
        
        # Publish trade opened
        await self.send_message(
            MessageType.TRADE_OPENED,
            {
                "trade_id": trade.trade_id,
                "proposal_id": trade.proposal_id,
                "ticker": trade.ticker,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "position_size": trade.position_size,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "entry_slippage": trade.entry_slippage,
                "timestamp": trade.opened_at.isoformat(),
            }
        )
        
    async def _check_trade_exit(self, trade: SimulatedTrade):
        """Check if trade should be exited."""
        
        # Get current price
        current_price = await self._get_current_price(trade.ticker)
        if not current_price:
            return
            
        exit_triggered = False
        exit_price = current_price
        exit_reason = None
        
        # Check stop loss
        if trade.direction == "long":
            if current_price <= trade.stop_loss:
                exit_triggered = True
                exit_price = trade.stop_loss
                exit_reason = ExitReason.STOP_HIT
        else:
            if current_price >= trade.stop_loss:
                exit_triggered = True
                exit_price = trade.stop_loss
                exit_reason = ExitReason.STOP_HIT
                
        # Check take profit
        if not exit_triggered:
            if trade.direction == "long":
                if current_price >= trade.take_profit:
                    exit_triggered = True
                    exit_price = trade.take_profit
                    exit_reason = ExitReason.TARGET_HIT
            else:
                if current_price <= trade.take_profit:
                    exit_triggered = True
                    exit_price = trade.take_profit
                    exit_reason = ExitReason.TARGET_HIT
                    
        # Check time stop
        if not exit_triggered and trade.opened_at:
            elapsed = (datetime.utcnow() - trade.opened_at).total_seconds() / 3600
            if elapsed > trade.time_stop_hours:
                exit_triggered = True
                exit_reason = ExitReason.TIME_STOP
                
        if exit_triggered:
            await self._execute_exit(trade, exit_price, exit_reason)
            
    async def _execute_exit(self, trade: SimulatedTrade, exit_price: float, reason: ExitReason):
        """Execute trade exit."""
        
        # Calculate slippage
        slippage = self._calculate_slippage(trade.ticker, trade.direction, "exit")
        
        if trade.direction == "long":
            fill_price = exit_price * (1 - slippage)
        else:
            fill_price = exit_price * (1 + slippage)
            
        # Create fill
        fill = SimulatedFill(
            fill_id=f"fill_{trade.trade_id}_exit",
            order_id=trade.trade_id,
            timestamp=datetime.utcnow(),
            price=fill_price,
            size=trade.position_size,
            direction="short" if trade.direction == "long" else "long",
            slippage=slippage,
            commission=self.commission_per_trade,
            fill_quality=self._classify_fill_quality(slippage),
        )
        
        trade.exit_fill = fill
        trade.exit_price = fill_price
        trade.exit_slippage = slippage
        trade.total_commission += self.commission_per_trade
        trade.exit_reason = reason
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.utcnow()
        
        # Calculate PnL
        if trade.direction == "long":
            gross_pnl = (fill_price - trade.entry_price) / trade.entry_price
        else:
            gross_pnl = (trade.entry_price - fill_price) / trade.entry_price
            
        trade.gross_pnl = gross_pnl
        trade.net_pnl = gross_pnl - (trade.total_commission / 10000)  # Assuming $10k position
        trade.return_pct = trade.net_pnl * 100
        
        self._fills.append(fill)
        
        # Update metrics
        self._metrics.total_commission = (
            (self._metrics.total_commission * (self._metrics.total_trades - 1) + trade.total_commission)
            / self._metrics.total_trades
        )
        
        if trade.net_pnl > 0:
            self._metrics.winning_trades += 1
        else:
            self._metrics.losing_trades += 1
            
        self._metrics.total_gross_pnl += trade.gross_pnl
        self._metrics.total_net_pnl += trade.net_pnl
        
        # Move to history
        self._trade_history.append(trade)
        del self._active_trades[trade.trade_id]
        
        # Publish trade closed
        await self.send_message(
            MessageType.TRADE_CLOSED,
            {
                "trade_id": trade.trade_id,
                "proposal_id": trade.proposal_id,
                "ticker": trade.ticker,
                "direction": trade.direction,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "gross_pnl": trade.gross_pnl,
                "net_pnl": trade.net_pnl,
                "return_pct": trade.return_pct,
                "exit_reason": trade.exit_reason.value if trade.exit_reason else None,
                "holding_time_hours": (trade.closed_at - trade.opened_at).total_seconds() / 3600 if trade.opened_at else 0,
                "timestamp": trade.closed_at.isoformat(),
            }
        )
        
        # Publish PnL update
        await self.send_message(
            MessageType.PNL_UPDATE,
            {
                "trade_id": trade.trade_id,
                "daily_pnl": self._calculate_daily_pnl(),
                "total_pnl": self._metrics.total_net_pnl,
                "win_rate": self._metrics.winning_trades / self._metrics.total_trades if self._metrics.total_trades > 0 else 0,
            }
        )
        
    def _calculate_slippage(self, ticker: str, direction: str, side: str) -> float:
        """Calculate realistic slippage."""
        
        # Base slippage
        slippage = self.base_slippage_pct
        
        # Add volatility component
        volatility = self._get_recent_volatility(ticker)
        slippage += volatility * self.volatility_slippage_factor
        
        # Add spread
        slippage += self.spread_pct / 2
        
        # Add random noise
        slippage *= (1 + np.random.normal(0, 0.3))
        
        # Ensure positive
        slippage = max(0.0001, slippage)
        
        return slippage
        
    def _classify_fill_quality(self, slippage: float) -> str:
        """Classify fill quality based on slippage."""
        if slippage < self.base_slippage_pct * 1.5:
            self._metrics.good_fills += 1
            return "good"
        elif slippage < self.base_slippage_pct * 3:
            self._metrics.fair_fills += 1
            return "fair"
        else:
            self._metrics.poor_fills += 1
            return "poor"
            
    def _get_recent_volatility(self, ticker: str) -> float:
        """Get recent volatility for a ticker."""
        prices = self._price_cache.get(ticker, [])
        if len(prices) < 20:
            return 0.01  # Default 1%
            
        closes = [p.get("close", 0) for p in prices[-20:]]
        returns = [abs(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] > 0]
        
        return np.mean(returns) if returns else 0.01
        
    async def _get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker."""
        prices = self._price_cache.get(ticker, [])
        if prices:
            return prices[-1].get("close")
        return None
        
    def _calculate_daily_pnl(self) -> float:
        """Calculate today's PnL."""
        today = datetime.utcnow().date()
        daily_pnl = 0
        
        for trade in self._trade_history:
            if trade.closed_at and trade.closed_at.date() == today:
                daily_pnl += trade.net_pnl
                
        return daily_pnl
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        
        if task_type == "get_trade":
            trade_id = task.get("trade_id")
            trade = self._active_trades.get(trade_id) or next(
                (t for t in self._trade_history if t.trade_id == trade_id), None
            )
            return {
                "trade": self._trade_to_dict(trade) if trade else None
            }
            
        elif task_type == "get_active_trades":
            return {
                "trades": [
                    self._trade_to_dict(t) for t in self._active_trades.values()
                ]
            }
            
        elif task_type == "get_trade_history":
            limit = task.get("limit", 100)
            return {
                "trades": [
                    self._trade_to_dict(t) for t in self._trade_history[-limit:]
                ],
                "total_count": len(self._trade_history),
            }
            
        elif task_type == "get_metrics":
            return {
                "metrics": {
                    "total_trades": self._metrics.total_trades,
                    "winning_trades": self._metrics.winning_trades,
                    "losing_trades": self._metrics.losing_trades,
                    "win_rate": self._metrics.winning_trades / self._metrics.total_trades if self._metrics.total_trades > 0 else 0,
                    "total_gross_pnl": self._metrics.total_gross_pnl,
                    "total_net_pnl": self._metrics.total_net_pnl,
                    "avg_entry_slippage": self._metrics.avg_entry_slippage,
                    "good_fills": self._metrics.good_fills,
                    "fair_fills": self._metrics.fair_fills,
                    "poor_fills": self._metrics.poor_fills,
                }
            }
            
        elif task_type == "manual_close":
            trade_id = task.get("trade_id")
            trade = self._active_trades.get(trade_id)
            if trade and trade.status == TradeStatus.OPEN:
                current_price = await self._get_current_price(trade.ticker)
                if current_price:
                    await self._execute_exit(trade, current_price, ExitReason.MANUAL)
                    return {"status": "closed", "trade_id": trade_id}
            return {"error": "Trade not found or not open"}
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _trade_to_dict(self, trade: SimulatedTrade) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        if not trade:
            return None
        return {
            "trade_id": trade.trade_id,
            "proposal_id": trade.proposal_id,
            "ticker": trade.ticker,
            "direction": trade.direction,
            "status": trade.status.value,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "position_size": trade.position_size,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "gross_pnl": trade.gross_pnl,
            "net_pnl": trade.net_pnl,
            "return_pct": trade.return_pct,
            "exit_reason": trade.exit_reason.value if trade.exit_reason else None,
            "entry_slippage": trade.entry_slippage,
            "exit_slippage": trade.exit_slippage,
            "total_commission": trade.total_commission,
            "created_at": trade.created_at.isoformat(),
            "opened_at": trade.opened_at.isoformat() if trade.opened_at else None,
            "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "active_trades": len(self._active_trades),
            "trade_history_count": len(self._trade_history),
            "total_fills": len(self._fills),
            "win_rate": self._metrics.winning_trades / self._metrics.total_trades if self._metrics.total_trades > 0 else 0,
            "total_pnl": self._metrics.total_net_pnl,
        })
        return status


import asyncio
