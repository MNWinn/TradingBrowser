"""Practice Trading Engine - Core paper trading functionality.

This module provides virtual portfolio management, paper trade execution,
position tracking, and P&L calculation for practice trading.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import PaperOrder
from app.services.execution import AdapterFactory
from app.services.risk import RiskEngine, RiskState


class PracticeTradeStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PracticePositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class PracticePosition:
    """Represents a virtual position in the practice portfolio."""
    
    ticker: str
    side: PracticePositionSide
    quantity: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    opened_at: datetime
    unrealized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    realized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    
    def update_price(self, new_price: Decimal) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = new_price
        if self.side == PracticePositionSide.LONG:
            self.unrealized_pnl = (self.current_price - self.avg_entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.avg_entry_price - self.current_price) * self.quantity
    
    @property
    def market_value(self) -> Decimal:
        """Calculate current market value of position."""
        return self.current_price * self.quantity
    
    @property
    def total_pnl(self) -> Decimal:
        """Calculate total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl


@dataclass
class PracticePortfolio:
    """Virtual portfolio for paper trading."""
    
    user_id: str
    initial_balance: Decimal
    cash_balance: Decimal
    positions: dict[str, PracticePosition] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def total_equity(self) -> Decimal:
        """Calculate total portfolio equity (cash + positions)."""
        positions_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash_balance + positions_value
    
    @property
    def total_pnl(self) -> Decimal:
        """Calculate total P&L across all positions."""
        return sum(pos.total_pnl for pos in self.positions.values())
    
    @property
    def total_pnl_percent(self) -> Decimal:
        """Calculate total P&L as percentage of initial balance."""
        if self.initial_balance == 0:
            return Decimal("0")
        return (self.total_pnl / self.initial_balance) * 100
    
    def get_position(self, ticker: str) -> PracticePosition | None:
        """Get position for a specific ticker."""
        return self.positions.get(ticker.upper())
    
    def update_position(self, position: PracticePosition) -> None:
        """Update or add a position."""
        self.positions[position.ticker.upper()] = position
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class PracticeTrade:
    """Represents a paper trade execution."""
    
    trade_id: str
    user_id: str
    ticker: str
    side: str  # buy, sell
    quantity: Decimal
    price: Decimal
    status: PracticeTradeStatus
    created_at: datetime
    filled_at: datetime | None = None
    commission: Decimal = field(default_factory=lambda: Decimal("0"))
    slippage: Decimal = field(default_factory=lambda: Decimal("0"))
    rationale: dict[str, Any] | None = None
    strategy_id: str | None = None
    
    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost including commission and slippage."""
        base_cost = self.price * self.quantity
        return base_cost + self.commission + self.slippage


class PracticeEngine:
    """Core engine for paper trading operations."""
    
    # Default commission rate (0.1%)
    DEFAULT_COMMISSION_RATE = Decimal("0.001")
    
    # Default slippage model (0.05% for market orders)
    DEFAULT_SLIPPAGE_RATE = Decimal("0.0005")
    
    def __init__(
        self,
        db: Session,
        commission_rate: Decimal | None = None,
        slippage_rate: Decimal | None = None,
    ):
        self.db = db
        self.commission_rate = commission_rate or self.DEFAULT_COMMISSION_RATE
        self.slippage_rate = slippage_rate or self.DEFAULT_SLIPPAGE_RATE
        self._portfolios: dict[str, PracticePortfolio] = {}
        self._risk_engine = RiskEngine({
            "max_daily_loss": float("inf"),
            "max_weekly_loss": float("inf"),
            "max_concurrent_positions": 50,
            "max_capital_per_trade": float("inf"),
        })
    
    def create_portfolio(
        self,
        user_id: str,
        initial_balance: Decimal = Decimal("100000.00"),
    ) -> PracticePortfolio:
        """Create a new practice portfolio for a user."""
        portfolio = PracticePortfolio(
            user_id=user_id,
            initial_balance=initial_balance,
            cash_balance=initial_balance,
        )
        self._portfolios[user_id] = portfolio
        return portfolio
    
    def get_portfolio(self, user_id: str) -> PracticePortfolio | None:
        """Get a user's practice portfolio."""
        return self._portfolios.get(user_id)
    
    def calculate_commission(self, quantity: Decimal, price: Decimal) -> Decimal:
        """Calculate commission for a trade."""
        trade_value = quantity * price
        commission = trade_value * self.commission_rate
        return commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def calculate_slippage(
        self,
        quantity: Decimal,
        price: Decimal,
        side: str,
        volatility: Decimal | None = None,
    ) -> Decimal:
        """Calculate slippage for a trade."""
        base_slippage = quantity * price * self.slippage_rate
        
        # Adjust for volatility if provided
        if volatility:
            base_slippage *= (Decimal("1") + volatility)
        
        return base_slippage.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def estimate_fill_price(
        self,
        ticker: str,
        side: str,
        market_price: Decimal,
        quantity: Decimal,
    ) -> Decimal:
        """Estimate realistic fill price with slippage."""
        slippage = self.calculate_slippage(quantity, market_price, side)
        slippage_per_share = slippage / quantity if quantity > 0 else Decimal("0")
        
        if side.lower() == "buy":
            return market_price + slippage_per_share
        else:
            return market_price - slippage_per_share
    
    async def execute_trade(
        self,
        user_id: str,
        ticker: str,
        side: str,
        quantity: Decimal,
        market_price: Decimal,
        order_type: str = "market",
        strategy_id: str | None = None,
        rationale: dict[str, Any] | None = None,
    ) -> PracticeTrade:
        """Execute a paper trade."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            raise ValueError(f"No portfolio found for user {user_id}")
        
        # Generate trade ID
        trade_id = f"practice_{uuid.uuid4().hex[:16]}"
        
        # Calculate fill price with slippage
        fill_price = self.estimate_fill_price(ticker, side, market_price, quantity)
        
        # Calculate costs
        commission = self.calculate_commission(quantity, fill_price)
        slippage = self.calculate_slippage(quantity, fill_price, side)
        
        total_cost = (fill_price * quantity) + commission + slippage
        
        # Validate trade
        if side.lower() == "buy":
            if total_cost > portfolio.cash_balance:
                trade = PracticeTrade(
                    trade_id=trade_id,
                    user_id=user_id,
                    ticker=ticker.upper(),
                    side=side,
                    quantity=quantity,
                    price=fill_price,
                    status=PracticeTradeStatus.REJECTED,
                    created_at=datetime.now(timezone.utc),
                    commission=commission,
                    slippage=slippage,
                    rationale={"error": "Insufficient funds", "requested": str(total_cost), "available": str(portfolio.cash_balance)},
                    strategy_id=strategy_id,
                )
                return trade
        
        # Create trade record
        trade = PracticeTrade(
            trade_id=trade_id,
            user_id=user_id,
            ticker=ticker.upper(),
            side=side,
            quantity=quantity,
            price=fill_price,
            status=PracticeTradeStatus.FILLED,
            created_at=datetime.now(timezone.utc),
            filled_at=datetime.now(timezone.utc),
            commission=commission,
            slippage=slippage,
            rationale=rationale,
            strategy_id=strategy_id,
        )
        
        # Update portfolio
        await self._update_portfolio_after_trade(portfolio, trade)
        
        # Persist to database
        await self._persist_trade(trade)
        
        return trade
    
    async def _update_portfolio_after_trade(
        self,
        portfolio: PracticePortfolio,
        trade: PracticeTrade,
    ) -> None:
        """Update portfolio state after a trade execution."""
        ticker = trade.ticker.upper()
        total_cost = trade.total_cost
        
        if trade.side.lower() == "buy":
            # Deduct cash
            portfolio.cash_balance -= total_cost
            
            # Update or create position
            existing = portfolio.get_position(ticker)
            if existing:
                # Average up the position
                total_qty = existing.quantity + trade.quantity
                total_value = (existing.avg_entry_price * existing.quantity) + (trade.price * trade.quantity)
                new_avg = total_value / total_qty if total_qty > 0 else Decimal("0")
                
                existing.quantity = total_qty
                existing.avg_entry_price = new_avg
                existing.update_price(trade.price)
            else:
                # New position
                position = PracticePosition(
                    ticker=ticker,
                    side=PracticePositionSide.LONG,
                    quantity=trade.quantity,
                    avg_entry_price=trade.price,
                    current_price=trade.price,
                    opened_at=trade.filled_at or datetime.now(timezone.utc),
                )
                portfolio.update_position(position)
        
        else:  # sell
            # Add cash
            portfolio.cash_balance += (trade.price * trade.quantity) - trade.commission - trade.slippage
            
            # Update or close position
            existing = portfolio.get_position(ticker)
            if existing:
                if trade.quantity >= existing.quantity:
                    # Close position
                    realized = (trade.price - existing.avg_entry_price) * existing.quantity
                    if existing.side == PracticePositionSide.SHORT:
                        realized = -realized
                    
                    existing.realized_pnl += realized
                    portfolio.positions.pop(ticker, None)
                else:
                    # Partial close
                    realized = (trade.price - existing.avg_entry_price) * trade.quantity
                    if existing.side == PracticePositionSide.SHORT:
                        realized = -realized
                    
                    existing.quantity -= trade.quantity
                    existing.realized_pnl += realized
                    existing.update_price(trade.price)
        
        portfolio.updated_at = datetime.now(timezone.utc)
    
    async def _persist_trade(self, trade: PracticeTrade) -> None:
        """Persist trade to database."""
        db_trade = PaperOrder(
            broker_order_id=trade.trade_id,
            ticker=trade.ticker,
            side=trade.side,
            qty=float(trade.quantity),
            order_type="market",  # Simplified for practice
            status=trade.status.value,
            rationale={
                "trade_id": trade.trade_id,
                "user_id": trade.user_id,
                "price": str(trade.price),
                "commission": str(trade.commission),
                "slippage": str(trade.slippage),
                "strategy_id": trade.strategy_id,
                "rationale": trade.rationale,
                "filled_at": trade.filled_at.isoformat() if trade.filled_at else None,
            },
        )
        self.db.add(db_trade)
        self.db.commit()
    
    def update_positions_prices(self, user_id: str, prices: dict[str, Decimal]) -> None:
        """Update all position prices with latest market data."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return
        
        for ticker, price in prices.items():
            position = portfolio.get_position(ticker)
            if position:
                position.update_price(price)
        
        portfolio.updated_at = datetime.now(timezone.utc)
    
    def get_portfolio_summary(self, user_id: str) -> dict[str, Any]:
        """Get a summary of the portfolio."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return {"error": "Portfolio not found"}
        
        return {
            "user_id": portfolio.user_id,
            "initial_balance": str(portfolio.initial_balance),
            "cash_balance": str(portfolio.cash_balance),
            "total_equity": str(portfolio.total_equity),
            "total_pnl": str(portfolio.total_pnl),
            "total_pnl_percent": float(portfolio.total_pnl_percent),
            "positions_count": len(portfolio.positions),
            "positions": [
                {
                    "ticker": pos.ticker,
                    "side": pos.side.value,
                    "quantity": str(pos.quantity),
                    "avg_entry_price": str(pos.avg_entry_price),
                    "current_price": str(pos.current_price),
                    "market_value": str(pos.market_value),
                    "unrealized_pnl": str(pos.unrealized_pnl),
                    "realized_pnl": str(pos.realized_pnl),
                }
                for pos in portfolio.positions.values()
            ],
            "created_at": portfolio.created_at.isoformat(),
            "updated_at": portfolio.updated_at.isoformat(),
        }
    
    def close_all_positions(
        self,
        user_id: str,
        market_prices: dict[str, Decimal],
    ) -> list[PracticeTrade]:
        """Close all open positions at current market prices."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return []
        
        closed_trades = []
        
        for ticker, position in list(portfolio.positions.items()):
            market_price = market_prices.get(ticker)
            if not market_price:
                continue
            
            side = "sell" if position.side == PracticePositionSide.LONG else "buy"
            
            import asyncio
            trade = asyncio.run(self.execute_trade(
                user_id=user_id,
                ticker=ticker,
                side=side,
                quantity=position.quantity,
                market_price=market_price,
                rationale={"action": "close_all_positions"},
            ))
            
            closed_trades.append(trade)
        
        return closed_trades
    
    def reset_portfolio(
        self,
        user_id: str,
        new_balance: Decimal | None = None,
    ) -> PracticePortfolio:
        """Reset portfolio to initial state."""
        portfolio = self.get_portfolio(user_id)
        if not portfolio:
            return self.create_portfolio(user_id, new_balance or Decimal("100000.00"))
        
        # Clear positions
        portfolio.positions.clear()
        
        # Reset balance
        portfolio.initial_balance = new_balance or portfolio.initial_balance
        portfolio.cash_balance = portfolio.initial_balance
        portfolio.total_pnl = Decimal("0")
        portfolio.updated_at = datetime.now(timezone.utc)
        
        return portfolio


# Global engine instance for dependency injection
_practice_engine: PracticeEngine | None = None


def get_practice_engine(db: Session) -> PracticeEngine:
    """Get or create the practice engine instance."""
    global _practice_engine
    if _practice_engine is None:
        _practice_engine = PracticeEngine(db)
    return _practice_engine
