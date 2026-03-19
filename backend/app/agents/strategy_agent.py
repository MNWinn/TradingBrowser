"""
Strategy Agent

Combines technical + predictive + contextual signals.
Formulates specific trade ideas with entry, stop, target, exit logic.
Calculates risk/reward and conviction scores.

Outputs:
- Trade proposals
- Rationale
- Risk/reward ratios
- Conviction scores
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class TradeDirection(Enum):
    """Direction of the trade."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class ConvictionLevel(Enum):
    """Conviction level for a trade."""
    VERY_HIGH = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    VERY_LOW = 1


@dataclass
class TradeProposal:
    """A proposed trade with full details."""
    proposal_id: str
    ticker: str
    timestamp: datetime
    
    # Trade details
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float  # Percentage of portfolio
    
    # Risk metrics
    risk_amount: float  # Dollar amount at risk
    risk_percent: float  # Percentage of portfolio at risk
    reward_amount: float  # Potential reward
    risk_reward_ratio: float
    
    # Conviction
    conviction_score: float  # 0.0 to 1.0
    conviction_level: ConvictionLevel
    
    # Rationale
    entry_rationale: List[str]
    exit_rationale: List[str]
    risk_rationale: List[str]
    
    # Signal sources
    technical_signals: Dict[str, Any]
    predictive_signals: Dict[str, Any]
    contextual_signals: Dict[str, Any]
    
    # Setup classification
    setup_type: str
    setup_quality: str  # A, B, C grade
    
    # Time parameters
    expected_hold_time: str
    timeframe: str
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None


@dataclass
class SignalAggregate:
    """Aggregated signals from multiple sources."""
    ticker: str
    timestamp: datetime
    
    # Technical
    trend_score: float  # -1.0 to 1.0
    momentum_score: float  # -1.0 to 1.0
    volume_score: float  # 0.0 to 1.0
    structure_score: float  # -1.0 to 1.0
    
    # Predictive
    predictive_direction: str
    predictive_confidence: float
    predictive_strength: float
    
    # Contextual
    regime: str
    regime_stability: float
    market_correlation: float
    sector_strength: float
    
    # Combined
    composite_score: float
    signal_agreement: float  # How much signals agree


class StrategyAgent(BaseAgent):
    """
    Agent for formulating trade ideas from multiple signal sources.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("strategy", message_bus, config)
        
        # Configuration
        self.min_conviction_threshold = config.get("min_conviction", 0.6) if config else 0.6
        self.min_risk_reward = config.get("min_risk_reward", 1.5) if config else 1.5
        self.max_position_size = config.get("max_position_size", 0.25) if config else 0.25
        
        # State
        self._signal_cache: Dict[str, SignalAggregate] = {}
        self._active_proposals: Dict[str, TradeProposal] = {}
        self._proposal_history: List[TradeProposal] = []
        
        # Signal weights
        self._signal_weights = {
            "technical": 0.35,
            "predictive": 0.35,
            "contextual": 0.30,
        }
        
        # Register handlers
        self.register_handler(MessageType.MARKET_STRUCTURE_UPDATE, self._handle_structure_update)
        self.register_handler(MessageType.MIROFISH_SIGNAL_UPDATE, self._handle_mirofish_signal)
        self.register_handler(MessageType.REGIME_CHANGE, self._handle_regime_change)
        
    async def _handle_structure_update(self, message: AgentMessage):
        """Handle market structure updates."""
        payload = message.payload
        ticker = payload.get("ticker")
        
        if ticker:
            await self._update_technical_signals(ticker, payload)
            
    async def _handle_mirofish_signal(self, message: AgentMessage):
        """Handle MiroFish signal updates."""
        payload = message.payload
        ticker = payload.get("ticker")
        
        if ticker:
            await self._update_predictive_signals(ticker, payload)
            
    async def _handle_regime_change(self, message: AgentMessage):
        """Handle regime change alerts."""
        payload = message.payload
        ticker = payload.get("ticker")
        new_regime = payload.get("new_regime")
        
        if ticker and new_regime:
            await self._update_contextual_signals(ticker, {"regime": new_regime})
            
    async def _update_technical_signals(self, ticker: str, data: Dict[str, Any]):
        """Update technical signal component."""
        if ticker not in self._signal_cache:
            self._signal_cache[ticker] = SignalAggregate(
                ticker=ticker,
                timestamp=datetime.utcnow(),
                trend_score=0,
                momentum_score=0,
                volume_score=0,
                structure_score=0,
                predictive_direction="neutral",
                predictive_confidence=0.5,
                predictive_strength=0.5,
                regime="unknown",
                regime_stability=0.5,
                market_correlation=0,
                sector_strength=0.5,
                composite_score=0,
                signal_agreement=0.5,
            )
            
        agg = self._signal_cache[ticker]
        agg.timestamp = datetime.utcnow()
        
        # Update technical scores
        agg.trend_score = 1.0 if data.get("trend_direction") == "up" else -1.0 if data.get("trend_direction") == "down" else 0
        agg.trend_score *= data.get("trend_strength", 0)
        
        agg.structure_score = data.get("structure_score", 0)
        
        # Momentum from RSI and MACD
        rsi = data.get("rsi", 50)
        macd_hist = data.get("macd_histogram", 0)
        agg.momentum_score = ((rsi - 50) / 50 + np.tanh(macd_hist)) / 2
        
        # Volume score
        vol_regime = data.get("volume_regime", "normal")
        agg.volume_score = 1.0 if vol_regime == "high" else 0.5 if vol_regime == "normal" else 0.2
        
        await self._recalculate_composite(ticker)
        
    async def _update_predictive_signals(self, ticker: str, data: Dict[str, Any]):
        """Update predictive signal component."""
        if ticker not in self._signal_cache:
            await self._update_technical_signals(ticker, {})
            
        agg = self._signal_cache[ticker]
        agg.timestamp = datetime.utcnow()
        
        agg.predictive_direction = data.get("direction", "neutral")
        agg.predictive_confidence = data.get("confidence", 0.5)
        agg.predictive_strength = data.get("strength", 0.5)
        
        await self._recalculate_composite(ticker)
        
    async def _update_contextual_signals(self, ticker: str, data: Dict[str, Any]):
        """Update contextual signal component."""
        if ticker not in self._signal_cache:
            await self._update_technical_signals(ticker, {})
            
        agg = self._signal_cache[ticker]
        agg.timestamp = datetime.utcnow()
        
        if "regime" in data:
            agg.regime = data["regime"]
        if "regime_stability" in data:
            agg.regime_stability = data["regime_stability"]
        if "market_correlation" in data:
            agg.market_correlation = data["market_correlation"]
        if "sector_strength" in data:
            agg.sector_strength = data["sector_strength"]
            
        await self._recalculate_composite(ticker)
        
    async def _recalculate_composite(self, ticker: str):
        """Recalculate composite signal score."""
        agg = self._signal_cache.get(ticker)
        if not agg:
            return
            
        # Technical contribution
        tech_score = (
            agg.trend_score * 0.4 +
            agg.momentum_score * 0.3 +
            agg.structure_score * 0.2 +
            (agg.volume_score - 0.5) * 2 * 0.1  # Normalize to -1 to 1
        )
        
        # Predictive contribution
        pred_direction = 1.0 if agg.predictive_direction == "bullish" else -1.0 if agg.predictive_direction == "bearish" else 0
        pred_score = pred_direction * agg.predictive_confidence * agg.predictive_strength
        
        # Contextual contribution
        regime_multiplier = 1.0
        if agg.regime in ["trending_up", "breakout"]:
            regime_multiplier = 1.2
        elif agg.regime in ["trending_down", "reversal"]:
            regime_multiplier = -1.2
        elif agg.regime == "ranging":
            regime_multiplier = 0.5
            
        context_score = regime_multiplier * agg.regime_stability * agg.sector_strength
        
        # Combined score
        agg.composite_score = (
            tech_score * self._signal_weights["technical"] +
            pred_score * self._signal_weights["predictive"] +
            context_score * self._signal_weights["contextual"]
        )
        
        # Signal agreement (how aligned are the signals)
        signals = [tech_score, pred_score, context_score]
        agg.signal_agreement = 1 - (np.std(signals) / (abs(np.mean(signals)) + 0.001))
        
        # Check if we should generate a proposal
        await self._evaluate_for_proposal(ticker)
        
    async def _evaluate_for_proposal(self, ticker: str):
        """Evaluate if we should generate a trade proposal."""
        agg = self._signal_cache.get(ticker)
        if not agg:
            return
            
        # Need strong signal and good agreement
        if abs(agg.composite_score) < self.min_conviction_threshold or agg.signal_agreement < 0.5:
            return
            
        # Check for existing active proposal
        for proposal in self._active_proposals.values():
            if proposal.ticker == ticker and not proposal.expires_at or proposal.expires_at > datetime.utcnow():
                return  # Already have an active proposal
                
        # Generate proposal
        await self._generate_proposal(ticker, agg)
        
    async def _generate_proposal(self, ticker: str, agg: SignalAggregate):
        """Generate a trade proposal from signal aggregate."""
        
        # Determine direction
        if agg.composite_score > 0:
            direction = TradeDirection.LONG
        elif agg.composite_score < 0:
            direction = TradeDirection.SHORT
        else:
            return  # Neutral, no trade
            
        # Get current price (from cache or default)
        current_price = 100.0  # Would be fetched from market data
        
        # Calculate entry, stop, target
        entry_price = current_price
        
        # ATR-based stop (simplified)
        atr_percent = 0.02  # 2% default
        if direction == TradeDirection.LONG:
            stop_loss = entry_price * (1 - atr_percent * 1.5)
            take_profit = entry_price * (1 + atr_percent * 3)  # 1:2 risk/reward
        else:
            stop_loss = entry_price * (1 + atr_percent * 1.5)
            take_profit = entry_price * (1 - atr_percent * 3)
            
        # Calculate risk metrics
        risk_per_share = abs(entry_price - stop_loss)
        reward_per_share = abs(take_profit - entry_price)
        risk_reward_ratio = reward_per_share / risk_per_share if risk_per_share > 0 else 0
        
        # Position sizing (Kelly criterion simplified)
        win_rate = 0.55  # Assumed from backtesting
        kelly = (win_rate * (risk_reward_ratio + 1) - 1) / risk_reward_ratio if risk_reward_ratio > 0 else 0
        kelly = max(0, min(kelly, self.max_position_size))  # Cap at max position size
        position_size = kelly * 0.25  # Use quarter Kelly for safety
        
        # Calculate conviction
        conviction_score = abs(agg.composite_score) * agg.signal_agreement
        conviction_level = self._score_to_conviction(conviction_score)
        
        # Build rationale
        entry_rationale = self._build_entry_rationale(agg, direction)
        exit_rationale = self._build_exit_rationale(agg, direction)
        risk_rationale = self._build_risk_rationale(agg, risk_reward_ratio)
        
        # Classify setup
        setup_type = self._classify_setup(agg, direction)
        setup_quality = self._grade_setup(conviction_score, risk_reward_ratio, agg.signal_agreement)
        
        proposal = TradeProposal(
            proposal_id=f"prop_{ticker}_{datetime.utcnow().timestamp()}",
            ticker=ticker,
            timestamp=datetime.utcnow(),
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            risk_amount=risk_per_share * position_size * 10000,  # Assuming $10k portfolio
            risk_percent=position_size * (risk_per_share / entry_price) * 100,
            reward_amount=reward_per_share * position_size * 10000,
            risk_reward_ratio=risk_reward_ratio,
            conviction_score=conviction_score,
            conviction_level=conviction_level,
            entry_rationale=entry_rationale,
            exit_rationale=exit_rationale,
            risk_rationale=risk_rationale,
            technical_signals={
                "trend_score": agg.trend_score,
                "momentum_score": agg.momentum_score,
                "structure_score": agg.structure_score,
            },
            predictive_signals={
                "direction": agg.predictive_direction,
                "confidence": agg.predictive_confidence,
                "strength": agg.predictive_strength,
            },
            contextual_signals={
                "regime": agg.regime,
                "regime_stability": agg.regime_stability,
            },
            setup_type=setup_type,
            setup_quality=setup_quality,
            expected_hold_time="1-3 days",
            timeframe="5m",
            tags=[setup_type, agg.regime, direction.value],
            expires_at=datetime.utcnow() + timedelta(hours=4),
        )
        
        self._active_proposals[proposal.proposal_id] = proposal
        self._proposal_history.append(proposal)
        
        # Publish proposal
        await self._publish_proposal(proposal)
        
    def _score_to_conviction(self, score: float) -> ConvictionLevel:
        """Convert score to conviction level."""
        if score >= 0.85:
            return ConvictionLevel.VERY_HIGH
        elif score >= 0.70:
            return ConvictionLevel.HIGH
        elif score >= 0.55:
            return ConvictionLevel.MEDIUM
        elif score >= 0.40:
            return ConvictionLevel.LOW
        else:
            return ConvictionLevel.VERY_LOW
            
    def _build_entry_rationale(self, agg: SignalAggregate, direction: TradeDirection) -> List[str]:
        """Build entry rationale from signals."""
        rationale = []
        
        # Technical
        if abs(agg.trend_score) > 0.5:
            trend = "strong uptrend" if agg.trend_score > 0 else "strong downtrend"
            rationale.append(f"Technical: {trend} detected (score: {agg.trend_score:.2f})")
            
        if abs(agg.momentum_score) > 0.5:
            mom = "bullish momentum" if agg.momentum_score > 0 else "bearish momentum"
            rationale.append(f"Momentum: {mom} (score: {agg.momentum_score:.2f})")
            
        # Predictive
        if agg.predictive_confidence > 0.6:
            rationale.append(f"MiroFish: {agg.predictive_direction} prediction with {agg.predictive_confidence:.0%} confidence")
            
        # Contextual
        if agg.regime_stability > 0.7:
            rationale.append(f"Regime: Stable {agg.regime} environment")
            
        return rationale
        
    def _build_exit_rationale(self, agg: SignalAggregate, direction: TradeDirection) -> List[str]:
        """Build exit rationale."""
        rationale = []
        
        if direction == TradeDirection.LONG:
            rationale.append("Target: 2:1 risk/reward based on ATR extension")
            rationale.append("Stop: 1.5x ATR below entry")
        else:
            rationale.append("Target: 2:1 risk/reward based on ATR extension")
            rationale.append("Stop: 1.5x ATR above entry")
            
        rationale.append("Time stop: Exit if not profitable within 3 days")
        
        return rationale
        
    def _build_risk_rationale(self, agg: SignalAggregate, risk_reward: float) -> List[str]:
        """Build risk rationale."""
        rationale = []
        
        rationale.append(f"Risk/Reward ratio: {risk_reward:.2f}")
        
        if agg.signal_agreement > 0.8:
            rationale.append("High signal agreement reduces uncertainty")
        elif agg.signal_agreement < 0.6:
            rationale.append("Caution: Mixed signals increase uncertainty")
            
        if agg.regime_stability < 0.5:
            rationale.append("Warning: Unstable regime increases risk")
            
        return rationale
        
    def _classify_setup(self, agg: SignalAggregate, direction: TradeDirection) -> str:
        """Classify the setup type."""
        if direction == TradeDirection.LONG:
            if agg.trend_score > 0.5 and agg.momentum_score > 0.3:
                return "trend_following"
            elif agg.momentum_score > 0.5 and agg.trend_score < 0.3:
                return "momentum_breakout"
            elif agg.predictive_confidence > 0.7:
                return "predictive_signal"
            else:
                return "mean_reversion"
        else:
            if agg.trend_score < -0.5 and agg.momentum_score < -0.3:
                return "trend_following"
            elif agg.momentum_score < -0.5:
                return "momentum_breakdown"
            elif agg.predictive_confidence > 0.7:
                return "predictive_signal"
            else:
                return "mean_reversion"
                
    def _grade_setup(self, conviction: float, risk_reward: float, agreement: float) -> str:
        """Grade the setup quality."""
        score = conviction * 0.4 + min(risk_reward / 3, 1) * 0.3 + agreement * 0.3
        
        if score >= 0.8:
            return "A"
        elif score >= 0.6:
            return "B"
        elif score >= 0.4:
            return "C"
        else:
            return "D"
            
    async def _publish_proposal(self, proposal: TradeProposal):
        """Publish trade proposal to the bus."""
        await self.send_message(
            MessageType.TRADE_PROPOSAL,
            {
                "proposal_id": proposal.proposal_id,
                "ticker": proposal.ticker,
                "timestamp": proposal.timestamp.isoformat(),
                "direction": proposal.direction.value,
                "entry_price": proposal.entry_price,
                "stop_loss": proposal.stop_loss,
                "take_profit": proposal.take_profit,
                "position_size": proposal.position_size,
                "risk_reward_ratio": proposal.risk_reward_ratio,
                "conviction_score": proposal.conviction_score,
                "conviction_level": proposal.conviction_level.name,
                "setup_type": proposal.setup_type,
                "setup_quality": proposal.setup_quality,
                "rationale": {
                    "entry": proposal.entry_rationale,
                    "exit": proposal.exit_rationale,
                    "risk": proposal.risk_rationale,
                },
                "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
            }
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        ticker = task.get("ticker")
        
        if task_type == "generate_proposal":
            if ticker and ticker in self._signal_cache:
                await self._generate_proposal(ticker, self._signal_cache[ticker])
                return {"status": "generated", "ticker": ticker}
            return {"error": "No signal cache for ticker"}
            
        elif task_type == "get_proposal":
            proposal_id = task.get("proposal_id")
            proposal = self._active_proposals.get(proposal_id)
            return {
                "proposal": self._proposal_to_dict(proposal) if proposal else None
            }
            
        elif task_type == "get_active_proposals":
            return {
                "proposals": [
                    self._proposal_to_dict(p) 
                    for p in self._active_proposals.values()
                ]
            }
            
        elif task_type == "get_signals":
            agg = self._signal_cache.get(ticker)
            return {
                "ticker": ticker,
                "signals": self._aggregate_to_dict(agg) if agg else None
            }
            
        elif task_type == "update_weights":
            weights = task.get("weights", {})
            self._signal_weights.update(weights)
            return {"status": "updated", "weights": self._signal_weights}
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _proposal_to_dict(self, proposal: TradeProposal) -> Dict[str, Any]:
        """Convert proposal to dictionary."""
        if not proposal:
            return None
        return {
            "proposal_id": proposal.proposal_id,
            "ticker": proposal.ticker,
            "timestamp": proposal.timestamp.isoformat(),
            "direction": proposal.direction.value,
            "entry_price": proposal.entry_price,
            "stop_loss": proposal.stop_loss,
            "take_profit": proposal.take_profit,
            "position_size": proposal.position_size,
            "risk_reward_ratio": proposal.risk_reward_ratio,
            "conviction_score": proposal.conviction_score,
            "conviction_level": proposal.conviction_level.name,
            "setup_type": proposal.setup_type,
            "setup_quality": proposal.setup_quality,
            "rationale": {
                "entry": proposal.entry_rationale,
                "exit": proposal.exit_rationale,
                "risk": proposal.risk_rationale,
            },
            "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
        }
        
    def _aggregate_to_dict(self, agg: SignalAggregate) -> Dict[str, Any]:
        """Convert signal aggregate to dictionary."""
        if not agg:
            return None
        return {
            "ticker": agg.ticker,
            "timestamp": agg.timestamp.isoformat(),
            "technical": {
                "trend_score": agg.trend_score,
                "momentum_score": agg.momentum_score,
                "volume_score": agg.volume_score,
                "structure_score": agg.structure_score,
            },
            "predictive": {
                "direction": agg.predictive_direction,
                "confidence": agg.predictive_confidence,
                "strength": agg.predictive_strength,
            },
            "contextual": {
                "regime": agg.regime,
                "regime_stability": agg.regime_stability,
            },
            "composite_score": agg.composite_score,
            "signal_agreement": agg.signal_agreement,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "signal_cache_count": len(self._signal_cache),
            "active_proposals": len(self._active_proposals),
            "proposal_history_count": len(self._proposal_history),
            "signal_weights": self._signal_weights,
        })
        return status


from datetime import timedelta
import asyncio
