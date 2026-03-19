"""
MiroFish Ensemble - Ensemble decision making with other agents.

Provides:
- Weight MiroFish signals with other agents
- Historical accuracy tracking
- Dynamic weight adjustment
- Conflict resolution
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable

from app.services.mirofish.mirofish_fleet import (
    MiroFishFleet,
    FleetAnalysis,
    DirectionalBias,
    get_fleet,
)
from app.services.mirofish.mirofish_cache import get_cache

logger = logging.getLogger(__name__)


class SignalSource(Enum):
    """Sources of trading signals."""
    MIROFISH = "mirofish"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    MARKET_STRUCTURE = "market_structure"
    PROBABILITY = "probability"
    NEWS_CATALYST = "news_catalyst"
    RISK = "risk"
    EXECUTION = "execution"
    MANUAL = "manual"


class Action(Enum):
    """Trading actions."""
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


@dataclass
class AgentSignal:
    """Signal from a single agent."""
    source: SignalSource
    action: Action
    confidence: float
    ticker: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_data: dict | None = None

    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "action": self.action.value,
            "confidence": self.confidence,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class WeightConfig:
    """Weight configuration for an agent."""
    source: SignalSource
    weight: float
    min_confidence_threshold: float = 0.3
    max_confidence_cap: float = 0.95
    accuracy_score: float = 0.5  # 0-1, updated based on historical performance
    recency_weight: float = 1.0  # Higher = more weight on recent signals
    timeframe_bias: dict[str, float] = field(default_factory=dict)


@dataclass
class EnsembleResult:
    """Result of ensemble decision making."""
    ticker: str
    consensus_action: Action
    consensus_confidence: float
    signal_breakdown: dict[str, Any]
    weighted_score: float
    agreement_ratio: float
    dissent_signals: list[dict]
    mirofish_contribution: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "consensus_action": self.consensus_action.value,
            "consensus_confidence": self.consensus_confidence,
            "signal_breakdown": self.signal_breakdown,
            "weighted_score": self.weighted_score,
            "agreement_ratio": self.agreement_ratio,
            "dissent_signals": self.dissent_signals,
            "mirofish_contribution": self.mirofish_contribution,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class HistoricalAccuracyTracker:
    """Tracks historical accuracy of signal sources."""

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self._accuracy_db: dict[SignalSource, dict] = {}
        self._outcomes: list[dict] = []

    def record_outcome(
        self,
        source: SignalSource,
        ticker: str,
        predicted_action: Action,
        actual_outcome: float,  # P&L from the trade
        timestamp: datetime | None = None,
    ) -> None:
        """Record the outcome of a signal for accuracy tracking."""
        outcome = {
            "source": source.value,
            "ticker": ticker,
            "predicted_action": predicted_action.value,
            "actual_outcome": actual_outcome,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "was_correct": actual_outcome > 0,
        }
        self._outcomes.append(outcome)

        # Update source accuracy
        if source not in self._accuracy_db:
            self._accuracy_db[source] = {"correct": 0, "total": 0, "total_pnl": 0.0}

        self._accuracy_db[source]["total"] += 1
        self._accuracy_db[source]["total_pnl"] += actual_outcome
        if actual_outcome > 0:
            self._accuracy_db[source]["correct"] += 1

    def get_accuracy(self, source: SignalSource) -> float:
        """Get accuracy score for a source (0-1)."""
        if source not in self._accuracy_db:
            return 0.5  # Default neutral accuracy

        data = self._accuracy_db[source]
        if data["total"] == 0:
            return 0.5

        return data["correct"] / data["total"]

    def get_average_pnl(self, source: SignalSource) -> float:
        """Get average P&L for a source."""
        if source not in self._accuracy_db:
            return 0.0

        data = self._accuracy_db[source]
        if data["total"] == 0:
            return 0.0

        return data["total_pnl"] / data["total"]

    def get_all_accuracies(self) -> dict[str, float]:
        """Get accuracy for all sources."""
        return {
            source.value: self.get_accuracy(source)
            for source in SignalSource
        }

    def get_best_performers(self, min_signals: int = 5) -> list[tuple[SignalSource, float]]:
        """Get best performing sources."""
        performers = []
        for source in SignalSource:
            if source in self._accuracy_db and self._accuracy_db[source]["total"] >= min_signals:
                performers.append((source, self.get_accuracy(source)))

        return sorted(performers, key=lambda x: x[1], reverse=True)


class DynamicWeightAdjuster:
    """Dynamically adjusts weights based on performance and market conditions."""

    def __init__(
        self,
        accuracy_tracker: HistoricalAccuracyTracker,
        adjustment_rate: float = 0.1,
        min_weight: float = 0.1,
        max_weight: float = 2.0,
    ):
        self.accuracy_tracker = accuracy_tracker
        self.adjustment_rate = adjustment_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self._base_weights: dict[SignalSource, float] = {}

    def set_base_weights(self, weights: dict[SignalSource, float]) -> None:
        """Set the base weights for sources."""
        self._base_weights = weights.copy()

    def adjust_weights(
        self,
        market_regime: str | None = None,
        volatility_regime: str | None = None,
    ) -> dict[SignalSource, float]:
        """
        Adjust weights based on accuracy and market conditions.
        
        Args:
            market_regime: "bull", "bear", "range", or None
            volatility_regime: "high", "low", "normal", or None
            
        Returns:
            Adjusted weights dictionary
        """
        adjusted = {}

        for source, base_weight in self._base_weights.items():
            weight = base_weight

            # Adjust by accuracy
            accuracy = self.accuracy_tracker.get_accuracy(source)
            accuracy_factor = 0.5 + accuracy  # 0.5 to 1.5 range
            weight *= accuracy_factor

            # Market regime adjustments
            if market_regime:
                weight = self._apply_market_regime_adjustment(source, weight, market_regime)

            # Volatility regime adjustments
            if volatility_regime:
                weight = self._apply_volatility_adjustment(source, weight, volatility_regime)

            # Clamp to bounds
            adjusted[source] = max(self.min_weight, min(self.max_weight, weight))

        return adjusted

    def _apply_market_regime_adjustment(
        self,
        source: SignalSource,
        weight: float,
        regime: str,
    ) -> float:
        """Apply market regime specific adjustments."""
        regime_multipliers = {
            "bull": {
                SignalSource.MIROFISH: 1.1,
                SignalSource.TECHNICAL: 1.0,
                SignalSource.SENTIMENT: 1.2,
                SignalSource.FUNDAMENTAL: 1.1,
            },
            "bear": {
                SignalSource.MIROFISH: 1.1,
                SignalSource.TECHNICAL: 1.1,
                SignalSource.SENTIMENT: 0.9,
                SignalSource.FUNDAMENTAL: 0.9,
            },
            "range": {
                SignalSource.MIROFISH: 0.9,
                SignalSource.TECHNICAL: 1.2,
                SignalSource.SENTIMENT: 0.8,
                SignalSource.FUNDAMENTAL: 0.9,
            },
        }

        multiplier = regime_multipliers.get(regime, {}).get(source, 1.0)
        return weight * multiplier

    def _apply_volatility_adjustment(
        self,
        source: SignalSource,
        weight: float,
        regime: str,
    ) -> float:
        """Apply volatility regime specific adjustments."""
        volatility_multipliers = {
            "high": {
                SignalSource.MIROFISH: 0.9,
                SignalSource.TECHNICAL: 1.1,
                SignalSource.RISK: 1.3,
            },
            "low": {
                SignalSource.MIROFISH: 1.1,
                SignalSource.TECHNICAL: 0.9,
                SignalSource.FUNDAMENTAL: 1.1,
            },
            "normal": {},
        }

        multiplier = volatility_multipliers.get(regime, {}).get(source, 1.0)
        return weight * multiplier


class ConflictResolver:
    """Resolves conflicts between different agent signals."""

    @staticmethod
    def resolve(
        signals: list[AgentSignal],
        weights: dict[SignalSource, float],
    ) -> tuple[Action, float, list[dict]]:
        """
        Resolve conflicts and determine consensus action.
        
        Returns:
            (consensus_action, confidence, dissent_signals)
        """
        if not signals:
            return Action.NO_TRADE, 0.0, []

        # Calculate weighted scores for each action
        action_scores: dict[Action, float] = {action: 0.0 for action in Action}
        action_confidences: dict[Action, list[float]] = {action: [] for action in Action}

        for signal in signals:
            weight = weights.get(signal.source, 1.0)
            action_scores[signal.action] += signal.confidence * weight
            action_confidences[signal.action].append(signal.confidence * weight)

        # Find the winning action
        consensus_action = max(action_scores, key=action_scores.get)
        total_score = sum(action_scores.values())

        if total_score == 0:
            return Action.NO_TRADE, 0.0, []

        consensus_confidence = action_scores[consensus_action] / total_score

        # Identify dissenting signals
        dissent_signals = []
        for signal in signals:
            if signal.action != consensus_action:
                dissent_signals.append({
                    "source": signal.source.value,
                    "action": signal.action.value,
                    "confidence": signal.confidence,
                    "reason": f"Disagrees with {consensus_action.value}",
                })

        return consensus_action, consensus_confidence, dissent_signals

    @staticmethod
    def explain_conflict(
        signals: list[AgentSignal],
        consensus: Action,
    ) -> str:
        """Generate human-readable explanation of conflict resolution."""
        action_counts = {}
        for signal in signals:
            action_counts[signal.action] = action_counts.get(signal.action, 0) + 1

        total = len(signals)
        explanations = []

        for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
            pct = (count / total) * 100
            explanations.append(f"{action.value}: {count}/{total} ({pct:.0f}%)")

        return f"Consensus: {consensus.value} | " + " | ".join(explanations)


class MiroFishEnsemble:
    """
    Ensemble decision making integrating MiroFish with other agents.
    
    Features:
    - Weight MiroFish signals with other agents
    - Historical accuracy tracking
    - Dynamic weight adjustment
    - Conflict resolution
    """

    DEFAULT_WEIGHTS = {
        SignalSource.MIROFISH: 1.5,
        SignalSource.TECHNICAL: 1.0,
        SignalSource.SENTIMENT: 0.8,
        SignalSource.FUNDAMENTAL: 0.9,
        SignalSource.MARKET_STRUCTURE: 1.0,
        SignalSource.PROBABILITY: 0.7,
        SignalSource.NEWS_CATALYST: 0.6,
        SignalSource.RISK: 1.2,
        SignalSource.EXECUTION: 0.5,
        SignalSource.MANUAL: 2.0,
    }

    def __init__(
        self,
        weights: dict[SignalSource, float] | None = None,
        enable_dynamic_adjustment: bool = True,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.accuracy_tracker = HistoricalAccuracyTracker()
        self.weight_adjuster = DynamicWeightAdjuster(self.accuracy_tracker)
        self.weight_adjuster.set_base_weights(self.weights)
        self.conflict_resolver = ConflictResolver()
        self.fleet = get_fleet()
        self.enable_dynamic_adjustment = enable_dynamic_adjustment

    async def ensemble_decision(
        self,
        ticker: str,
        agent_signals: list[AgentSignal] | None = None,
        include_mirofish_deep: bool = True,
        market_regime: str | None = None,
        volatility_regime: str | None = None,
    ) -> EnsembleResult:
        """
        Generate ensemble decision combining MiroFish with other agents.
        
        Args:
            ticker: Stock symbol
            agent_signals: Optional pre-collected signals from other agents
            include_mirofish_deep: Whether to use deep MiroFish analysis
            market_regime: Current market regime ("bull", "bear", "range")
            volatility_regime: Volatility regime ("high", "low", "normal")
            
        Returns:
            EnsembleResult with consensus decision
        """
        ticker = ticker.upper()
        signals: list[AgentSignal] = list(agent_signals) if agent_signals else []

        # Get MiroFish signal
        mirofish_signal = await self._get_mirofish_signal(
            ticker,
            deep=include_mirofish_deep,
        )
        signals.append(mirofish_signal)

        # Adjust weights if dynamic adjustment enabled
        current_weights = self.weights
        if self.enable_dynamic_adjustment:
            current_weights = self.weight_adjuster.adjust_weights(
                market_regime=market_regime,
                volatility_regime=volatility_regime,
            )

        # Resolve conflicts
        consensus_action, consensus_confidence, dissent = self.conflict_resolver.resolve(
            signals,
            current_weights,
        )

        # Calculate weighted score
        weighted_score = self._calculate_weighted_score(signals, current_weights)

        # Calculate agreement ratio
        agreement_ratio = self._calculate_agreement_ratio(signals, consensus_action)

        # Build signal breakdown
        signal_breakdown = self._build_signal_breakdown(signals, current_weights)

        return EnsembleResult(
            ticker=ticker,
            consensus_action=consensus_action,
            consensus_confidence=consensus_confidence,
            signal_breakdown=signal_breakdown,
            weighted_score=weighted_score,
            agreement_ratio=agreement_ratio,
            dissent_signals=dissent,
            mirofish_contribution={
                "signal": mirofish_signal.to_dict(),
                "weight": current_weights.get(SignalSource.MIROFISH, 1.5),
                "influence": self._calculate_mirofish_influence(signals, current_weights),
            },
            metadata={
                "market_regime": market_regime,
                "volatility_regime": volatility_regime,
                "total_signals": len(signals),
                "weights_used": {k.value: v for k, v in current_weights.items()},
            },
        )

    async def _get_mirofish_signal(
        self,
        ticker: str,
        deep: bool = True,
    ) -> AgentSignal:
        """Get signal from MiroFish."""
        # Import here to avoid circular imports
        from app.services.mirofish import mirofish_predict, mirofish_deep_swarm
        
        try:
            if deep:
                result = await mirofish_deep_swarm({"ticker": ticker})
                bias = result.get("overall_bias", "NEUTRAL")
                confidence = result.get("overall_confidence", 0.5)
            else:
                result = await mirofish_predict({"ticker": ticker})
                bias = result.get("directional_bias", "NEUTRAL")
                confidence = result.get("confidence", 0.5)

            action = self._bias_to_action(bias)

            return AgentSignal(
                source=SignalSource.MIROFISH,
                action=action,
                confidence=confidence,
                ticker=ticker,
                raw_data=result,
            )
        except Exception as e:
            logger.error(f"MiroFish signal error for {ticker}: {e}")
            return AgentSignal(
                source=SignalSource.MIROFISH,
                action=Action.NO_TRADE,
                confidence=0.0,
                ticker=ticker,
                metadata={"error": str(e)},
            )

    def _bias_to_action(self, bias: str) -> Action:
        """Convert directional bias to action."""
        bias_upper = bias.upper()
        if bias_upper == "BULLISH":
            return Action.LONG
        elif bias_upper == "BEARISH":
            return Action.SHORT
        else:
            return Action.WAIT

    def _calculate_weighted_score(
        self,
        signals: list[AgentSignal],
        weights: dict[SignalSource, float],
    ) -> float:
        """Calculate overall weighted score (-1 to 1, negative = bearish)."""
        score = 0.0
        total_weight = 0.0

        for signal in signals:
            weight = weights.get(signal.source, 1.0)
            direction = 1.0 if signal.action == Action.LONG else (-1.0 if signal.action == Action.SHORT else 0.0)
            score += direction * signal.confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return round(score / total_weight, 4)

    def _calculate_agreement_ratio(
        self,
        signals: list[AgentSignal],
        consensus: Action,
    ) -> float:
        """Calculate ratio of signals agreeing with consensus."""
        if not signals:
            return 0.0

        agreeing = sum(1 for s in signals if s.action == consensus)
        return agreeing / len(signals)

    def _build_signal_breakdown(
        self,
        signals: list[AgentSignal],
        weights: dict[SignalSource, float],
    ) -> dict:
        """Build detailed breakdown of all signals."""
        breakdown = {
            "by_source": {},
            "by_action": {},
            "weighted_contributions": {},
        }

        for signal in signals:
            source_key = signal.source.value
            breakdown["by_source"][source_key] = {
                "action": signal.action.value,
                "confidence": signal.confidence,
                "weight": weights.get(signal.source, 1.0),
            }

            action_key = signal.action.value
            if action_key not in breakdown["by_action"]:
                breakdown["by_action"][action_key] = []
            breakdown["by_action"][action_key].append(source_key)

            # Weighted contribution
            direction = 1.0 if signal.action == Action.LONG else (-1.0 if signal.action == Action.SHORT else 0.0)
            breakdown["weighted_contributions"][source_key] = round(
                direction * signal.confidence * weights.get(signal.source, 1.0),
                4,
            )

        return breakdown

    def _calculate_mirofish_influence(
        self,
        signals: list[AgentSignal],
        weights: dict[SignalSource, float],
    ) -> float:
        """Calculate MiroFish's relative influence in the ensemble."""
        total_weight = sum(weights.get(s.source, 1.0) for s in signals)
        mirofish_weight = weights.get(SignalSource.MIROFISH, 1.5)

        if total_weight == 0:
            return 0.0

        return round(mirofish_weight / total_weight, 4)

    def record_outcome(
        self,
        source: SignalSource,
        ticker: str,
        predicted_action: Action,
        actual_pnl: float,
    ) -> None:
        """Record outcome for accuracy tracking."""
        self.accuracy_tracker.record_outcome(
            source=source,
            ticker=ticker,
            predicted_action=predicted_action,
            actual_outcome=actual_pnl,
        )

    def get_accuracy_report(self) -> dict:
        """Get comprehensive accuracy report."""
        return {
            "by_source": self.accuracy_tracker.get_all_accuracies(),
            "best_performers": [
                {"source": s.value, "accuracy": a}
                for s, a in self.accuracy_tracker.get_best_performers(min_signals=1)
            ],
            "average_pnls": {
                s.value: self.accuracy_tracker.get_average_pnl(s)
                for s in SignalSource
            },
        }

    def update_weights(self, new_weights: dict[SignalSource, float]) -> None:
        """Update base weights."""
        self.weights = new_weights
        self.weight_adjuster.set_base_weights(new_weights)


# Convenience functions
_ensemble: MiroFishEnsemble | None = None


def get_ensemble(enable_dynamic: bool = True) -> MiroFishEnsemble:
    """Get or create the singleton ensemble instance."""
    global _ensemble
    if _ensemble is None:
        _ensemble = MiroFishEnsemble(enable_dynamic_adjustment=enable_dynamic)
    return _ensemble


async def ensemble_decision(
    ticker: str,
    agent_signals: list[AgentSignal] | None = None,
    include_mirofish_deep: bool = True,
) -> dict:
    """Convenience function for ensemble decision."""
    ensemble = get_ensemble()
    result = await ensemble.ensemble_decision(
        ticker=ticker,
        agent_signals=agent_signals,
        include_mirofish_deep=include_mirofish_deep,
    )
    return result.to_dict()


def create_agent_signal(
    source: str,
    action: str,
    confidence: float,
    ticker: str,
    metadata: dict | None = None,
) -> AgentSignal:
    """Helper to create an AgentSignal."""
    return AgentSignal(
        source=SignalSource(source.lower()),
        action=Action(action.upper()),
        confidence=confidence,
        ticker=ticker.upper(),
        metadata=metadata or {},
    )
