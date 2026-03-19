"""
MiroFish Comparison - Compare MiroFish signals with other sources.

Provides:
- MiroFish vs Technical Analysis
- MiroFish vs Market Regime
- Agreement/disagreement analysis
- Which signal source is more accurate?
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

from app.services.mirofish_service import mirofish_predict, mirofish_deep_swarm
from app.services.mirofish.mirofish_fleet import DirectionalBias
from app.services.mirofish.mirofish_ensemble import SignalSource, Action

logger = logging.getLogger(__name__)


# Database Models
class MiroFishComparison(Base):
    """Database model for storing signal comparisons."""
    __tablename__ = "mirofish_comparisons"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Signals compared
    mirofish_bias = Column(String(20), nullable=False)
    mirofish_confidence = Column(Float, nullable=False)
    
    technical_bias = Column(String(20), nullable=True)
    technical_confidence = Column(Float, nullable=True)
    
    market_regime = Column(String(50), nullable=True)
    sentiment_bias = Column(String(20), nullable=True)
    
    # Agreement metrics
    agreement_score = Column(Float, nullable=False)
    disagreement_count = Column(Integer, default=0)
    
    # Detailed comparison
    comparison_data = Column(JSON, default=dict)
    accuracy_tracking = Column(JSON, default=dict)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    prediction_metadata = Column(JSON, default=dict)


class MiroFishAccuracyTracking(Base):
    """Database model for tracking signal accuracy over time."""
    __tablename__ = "mirofish_accuracy_tracking"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Signal source
    source = Column(String(50), nullable=False)  # mirofish, technical, combined, etc.
    
    # Prediction
    predicted_bias = Column(String(20), nullable=False)
    predicted_confidence = Column(Float, nullable=False)
    
    # Outcome (filled in later)
    actual_return = Column(Float, nullable=True)
    actual_direction = Column(String(20), nullable=True)  # UP, DOWN, FLAT
    was_correct = Column(Boolean, nullable=True)
    
    # Performance metrics
    pnl_potential = Column(Float, nullable=True)  # What would have been made
    holding_days = Column(Integer, nullable=True)
    
    # Resolution
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_price = Column(Float, nullable=True)


class SignalSourceType(Enum):
    """Types of signal sources."""
    MIROFISH = "mirofish"
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    MARKET_REGIME = "market_regime"
    NEWS = "news"
    VOLUME = "volume"
    COMBINED = "combined"


class AgreementLevel(Enum):
    """Level of agreement between signals."""
    STRONG_AGREE = "strong_agree"  # > 80%
    AGREE = "agree"  # 60-80%
    NEUTRAL = "neutral"  # 40-60%
    DISAGREE = "disagree"  # 20-40%
    STRONG_DISAGREE = "strong_disagree"  # < 20%


@dataclass
class SignalComparison:
    """Comparison between two signals."""
    source_1: SignalSourceType
    source_2: SignalSourceType
    bias_1: str
    bias_2: str
    confidence_1: float
    confidence_2: float
    agreement_score: float  # 0-1, higher = more agreement
    
    def to_dict(self) -> dict:
        return {
            "source_1": self.source_1.value,
            "source_2": self.source_2.value,
            "bias_1": self.bias_1,
            "bias_2": self.bias_2,
            "confidence_1": round(self.confidence_1, 4),
            "confidence_2": round(self.confidence_2, 4),
            "agreement_score": round(self.agreement_score, 4),
            "agreement_level": self.classify_agreement(),
            "is_aligned": self.bias_1 == self.bias_2,
        }
    
    def classify_agreement(self) -> str:
        """Classify the agreement level."""
        if self.agreement_score >= 0.8:
            return AgreementLevel.STRONG_AGREE.value
        elif self.agreement_score >= 0.6:
            return AgreementLevel.AGREE.value
        elif self.agreement_score >= 0.4:
            return AgreementLevel.NEUTRAL.value
        elif self.agreement_score >= 0.2:
            return AgreementLevel.DISAGREE.value
        else:
            return AgreementLevel.STRONG_DISAGREE.value


@dataclass
class SourceAccuracy:
    """Accuracy metrics for a signal source."""
    source: SignalSourceType
    total_signals: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    
    # Performance
    avg_confidence_when_correct: float = 0.0
    avg_confidence_when_wrong: float = 0.0
    avg_return_when_correct: float = 0.0
    avg_return_when_wrong: float = 0.0
    
    # By direction
    bullish_accuracy: float = 0.0
    bearish_accuracy: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "source": self.source.value,
            "total_signals": self.total_signals,
            "correct_predictions": self.correct_predictions,
            "accuracy": round(self.accuracy, 4),
            "avg_confidence_when_correct": round(self.avg_confidence_when_correct, 4),
            "avg_confidence_when_wrong": round(self.avg_confidence_when_wrong, 4),
            "avg_return_when_correct": round(self.avg_return_when_correct, 4),
            "avg_return_when_wrong": round(self.avg_return_when_wrong, 4),
            "bullish_accuracy": round(self.bullish_accuracy, 4),
            "bearish_accuracy": round(self.bearish_accuracy, 4),
        }


@dataclass
class ComprehensiveComparison:
    """Complete comparison of multiple signal sources."""
    id: str
    ticker: str
    timestamp: datetime
    
    # Individual signals
    signals: dict[str, dict] = field(default_factory=dict)
    
    # Pairwise comparisons
    comparisons: list[SignalComparison] = field(default_factory=list)
    
    # Overall agreement
    overall_agreement_score: float = 0.0
    consensus_bias: str = "NEUTRAL"
    consensus_confidence: float = 0.0
    
    # Disagreement analysis
    disagreements: list[dict] = field(default_factory=list)
    
    # Accuracy tracking
    accuracy_ranking: list[SourceAccuracy] = field(default_factory=list)
    
    # Metadata
    timeframe: str = "5m"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "timeframe": self.timeframe,
            "signals": self.signals,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "overall_agreement": {
                "score": round(self.overall_agreement_score, 4),
                "level": self._classify_overall_agreement(),
                "consensus_bias": self.consensus_bias,
                "consensus_confidence": round(self.consensus_confidence, 4),
            },
            "disagreements": self.disagreements,
            "accuracy_ranking": [a.to_dict() for a in self.accuracy_ranking],
            "recommendation": self.generate_recommendation(),
            "metadata": self.metadata,
        }
    
    def _classify_overall_agreement(self) -> str:
        """Classify overall agreement level."""
        if self.overall_agreement_score >= 0.8:
            return AgreementLevel.STRONG_AGREE.value
        elif self.overall_agreement_score >= 0.6:
            return AgreementLevel.AGREE.value
        elif self.overall_agreement_score >= 0.4:
            return AgreementLevel.NEUTRAL.value
        elif self.overall_agreement_score >= 0.2:
            return AgreementLevel.DISAGREE.value
        else:
            return AgreementLevel.STRONG_DISAGREE.value
    
    def generate_recommendation(self) -> str:
        """Generate trading recommendation based on comparison."""
        if self.overall_agreement_score >= 0.7 and self.consensus_bias != "NEUTRAL":
            return f"Strong {self.consensus_bias} signal - high confidence due to source agreement"
        elif self.overall_agreement_score >= 0.5 and self.consensus_bias != "NEUTRAL":
            return f"Moderate {self.consensus_bias} signal - some disagreement between sources"
        elif self.overall_agreement_score < 0.4:
            return "Sources disagree significantly - exercise caution or wait for clarity"
        else:
            return "No clear signal - neutral stance recommended"


class SignalComparator:
    """
    Compares MiroFish signals with other signal sources.
    
    Features:
    - Compare with technical analysis
    - Compare with market regime
    - Agreement/disagreement analysis
    - Track which sources are more accurate
    """
    
    def __init__(self):
        self._accuracy_db: dict[str, list[dict]] = {}
    
    async def compare_signals(
        self,
        ticker: str,
        timeframe: str = "5m",
        include_sources: list[str] | None = None,
    ) -> ComprehensiveComparison:
        """
        Compare MiroFish signals with other sources.
        
        Args:
            ticker: Stock symbol
            timeframe: Analysis timeframe
            include_sources: List of sources to include (default: all)
            
        Returns:
            ComprehensiveComparison with all comparisons
        """
        ticker = ticker.upper()
        comparison_id = f"cmp_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        sources_to_include = include_sources or [
            "mirofish", "technical", "sentiment", "market_regime"
        ]
        
        # Collect signals from all sources
        signals = {}
        
        # MiroFish signal
        if "mirofish" in sources_to_include:
            mirofish_signal = await self._get_mirofish_signal(ticker, timeframe)
            signals["mirofish"] = mirofish_signal
        
        # Technical analysis signal (simulated)
        if "technical" in sources_to_include:
            technical_signal = await self._get_technical_signal(ticker, timeframe)
            signals["technical"] = technical_signal
        
        # Market regime signal (simulated)
        if "market_regime" in sources_to_include:
            regime_signal = await self._get_market_regime_signal(ticker, timeframe)
            signals["market_regime"] = regime_signal
        
        # Sentiment signal (simulated)
        if "sentiment" in sources_to_include:
            sentiment_signal = await self._get_sentiment_signal(ticker, timeframe)
            signals["sentiment"] = sentiment_signal
        
        # Generate pairwise comparisons
        comparisons = self._generate_comparisons(signals)
        
        # Calculate overall agreement
        overall_agreement, consensus_bias, consensus_confidence = self._calculate_consensus(
            signals, comparisons
        )
        
        # Identify disagreements
        disagreements = self._identify_disagreements(comparisons)
        
        # Get accuracy ranking
        accuracy_ranking = await self._get_accuracy_ranking(ticker)
        
        comparison = ComprehensiveComparison(
            id=comparison_id,
            ticker=ticker,
            timestamp=datetime.now(timezone.utc),
            signals=signals,
            comparisons=comparisons,
            overall_agreement_score=overall_agreement,
            consensus_bias=consensus_bias,
            consensus_confidence=consensus_confidence,
            disagreements=disagreements,
            accuracy_ranking=accuracy_ranking,
            timeframe=timeframe,
            metadata={
                "sources_included": list(signals.keys()),
                "num_comparisons": len(comparisons),
            },
        )
        
        # Store in database
        await self._store_comparison(comparison)
        
        return comparison
    
    async def _get_mirofish_signal(self, ticker: str, timeframe: str) -> dict:
        """Get MiroFish signal."""
        try:
            result = await mirofish_predict({
                "ticker": ticker,
                "timeframe": timeframe,
            })
            return {
                "source": "mirofish",
                "bias": result.get("directional_bias", "NEUTRAL"),
                "confidence": result.get("confidence", 0.5),
                "raw": result,
            }
        except Exception as e:
            logger.error(f"Error getting MiroFish signal: {e}")
            return {
                "source": "mirofish",
                "bias": "NEUTRAL",
                "confidence": 0.0,
                "error": str(e),
            }
    
    async def _get_technical_signal(self, ticker: str, timeframe: str) -> dict:
        """
        Get technical analysis signal.
        
        In production, this would call a technical analysis service.
        For now, we simulate based on MiroFish data.
        """
        # Simulate technical signal
        # In reality, this would calculate RSI, MACD, moving averages, etc.
        
        # For simulation, we'll derive from MiroFish with some variation
        mirofish = await self._get_mirofish_signal(ticker, timeframe)
        mirofish_bias = mirofish.get("bias", "NEUTRAL")
        mirofish_conf = mirofish.get("confidence", 0.5)
        
        # Technical often agrees with MiroFish but with different confidence
        import random
        if random.random() < 0.7:  # 70% agreement
            tech_bias = mirofish_bias
            tech_conf = min(0.95, mirofish_conf * random.uniform(0.8, 1.2))
        else:
            # Disagree
            tech_bias = "BEARISH" if mirofish_bias == "BULLISH" else "BULLISH" if mirofish_bias == "BEARISH" else "NEUTRAL"
            tech_conf = mirofish_conf * random.uniform(0.5, 0.8)
        
        return {
            "source": "technical",
            "bias": tech_bias,
            "confidence": round(tech_conf, 4),
            "indicators": {
                "rsi": random.uniform(30, 70),
                "macd": "bullish" if tech_bias == "BULLISH" else "bearish",
                "trend": "uptrend" if tech_bias == "BULLISH" else "downtrend",
            },
        }
    
    async def _get_market_regime_signal(self, ticker: str, timeframe: str) -> dict:
        """Get market regime signal."""
        # Simulate market regime detection
        regimes = ["bull", "bear", "range", "volatile"]
        import random
        regime = random.choice(regimes)
        
        regime_bias_map = {
            "bull": "BULLISH",
            "bear": "BEARISH",
            "range": "NEUTRAL",
            "volatile": "NEUTRAL",
        }
        
        return {
            "source": "market_regime",
            "bias": regime_bias_map[regime],
            "confidence": random.uniform(0.5, 0.8),
            "regime": regime,
            "volatility_regime": "high" if regime == "volatile" else "normal",
        }
    
    async def _get_sentiment_signal(self, ticker: str, timeframe: str) -> dict:
        """Get sentiment signal."""
        import random
        
        # Simulate sentiment analysis
        sentiment_score = random.uniform(-1, 1)
        
        if sentiment_score > 0.3:
            bias = "BULLISH"
        elif sentiment_score < -0.3:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {
            "source": "sentiment",
            "bias": bias,
            "confidence": abs(sentiment_score),
            "sentiment_score": round(sentiment_score, 4),
            "social_volume": random.randint(1000, 10000),
            "news_sentiment": "positive" if bias == "BULLISH" else "negative" if bias == "BEARISH" else "neutral",
        }
    
    def _generate_comparisons(
        self,
        signals: dict[str, dict],
    ) -> list[SignalComparison]:
        """Generate pairwise comparisons between signals."""
        comparisons = []
        sources = list(signals.keys())
        
        for i, source_1 in enumerate(sources):
            for source_2 in sources[i+1:]:
                signal_1 = signals[source_1]
                signal_2 = signals[source_2]
                
                bias_1 = signal_1.get("bias", "NEUTRAL")
                bias_2 = signal_2.get("bias", "NEUTRAL")
                conf_1 = signal_1.get("confidence", 0.5)
                conf_2 = signal_2.get("confidence", 0.5)
                
                # Calculate agreement score
                agreement = self._calculate_agreement(bias_1, bias_2, conf_1, conf_2)
                
                comparisons.append(SignalComparison(
                    source_1=SignalSourceType(source_1),
                    source_2=SignalSourceType(source_2),
                    bias_1=bias_1,
                    bias_2=bias_2,
                    confidence_1=conf_1,
                    confidence_2=conf_2,
                    agreement_score=agreement,
                ))
        
        return comparisons
    
    def _calculate_agreement(
        self,
        bias_1: str,
        bias_2: str,
        conf_1: float,
        conf_2: float,
    ) -> float:
        """Calculate agreement score between two signals."""
        bias_1 = bias_1.upper()
        bias_2 = bias_2.upper()
        
        if bias_1 == bias_2:
            # Same bias - agreement based on confidence
            base_agreement = 0.7 + 0.3 * min(conf_1, conf_2)
        elif (bias_1 == "NEUTRAL" or bias_2 == "NEUTRAL"):
            # One is neutral - partial agreement
            base_agreement = 0.4 + 0.2 * min(conf_1, conf_2)
        else:
            # Opposite biases - disagreement
            base_agreement = 0.3 * (1 - max(conf_1, conf_2))
        
        return round(base_agreement, 4)
    
    def _calculate_consensus(
        self,
        signals: dict[str, dict],
        comparisons: list[SignalComparison],
    ) -> tuple[float, str, float]:
        """Calculate overall consensus from signals."""
        if not signals:
            return 0.0, "NEUTRAL", 0.0
        
        # Count votes weighted by confidence
        votes = {"BULLISH": 0.0, "BEARISH": 0.0, "NEUTRAL": 0.0}
        total_confidence = 0.0
        
        for source, signal in signals.items():
            bias = signal.get("bias", "NEUTRAL").upper()
            conf = signal.get("confidence", 0.5)
            votes[bias] += conf
            total_confidence += conf
        
        # Determine consensus bias
        consensus_bias = max(votes, key=votes.get)
        consensus_confidence = votes[consensus_bias] / total_confidence if total_confidence > 0 else 0
        
        # Calculate overall agreement
        if comparisons:
            overall_agreement = sum(c.agreement_score for c in comparisons) / len(comparisons)
        else:
            overall_agreement = 0.5
        
        return round(overall_agreement, 4), consensus_bias, round(consensus_confidence, 4)
    
    def _identify_disagreements(self, comparisons: list[SignalComparison]) -> list[dict]:
        """Identify significant disagreements."""
        disagreements = []
        
        for comp in comparisons:
            if comp.agreement_score < 0.5:
                disagreements.append({
                    "sources": [comp.source_1.value, comp.source_2.value],
                    "bias_1": comp.bias_1,
                    "bias_2": comp.bias_2,
                    "agreement_score": comp.agreement_score,
                    "severity": "high" if comp.agreement_score < 0.3 else "medium",
                    "explanation": f"{comp.source_1.value} suggests {comp.bias_1} but {comp.source_2.value} suggests {comp.bias_2}",
                })
        
        return disagreements
    
    async def _get_accuracy_ranking(self, ticker: str) -> list[SourceAccuracy]:
        """Get accuracy ranking for signal sources."""
        # Query database for historical accuracy
        try:
            db = next(get_db())
            
            # Get records for this ticker from last 90 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            
            records = db.query(MiroFishAccuracyTracking).filter(
                MiroFishAccuracyTracking.ticker == ticker,
                MiroFishAccuracyTracking.resolved_at >= cutoff,
                MiroFishAccuracyTracking.was_correct.isnot(None)
            ).all()
            
            # Calculate accuracy by source
            source_stats: dict[str, dict] = {}
            
            for record in records:
                source = record.source
                if source not in source_stats:
                    source_stats[source] = {
                        "total": 0,
                        "correct": 0,
                        "conf_correct": [],
                        "conf_wrong": [],
                        "return_correct": [],
                        "return_wrong": [],
                        "bullish_total": 0,
                        "bullish_correct": 0,
                        "bearish_total": 0,
                        "bearish_correct": 0,
                    }
                
                stats = source_stats[source]
                stats["total"] += 1
                
                if record.was_correct:
                    stats["correct"] += 1
                    stats["conf_correct"].append(record.predicted_confidence)
                    stats["return_correct"].append(record.actual_return or 0)
                else:
                    stats["conf_wrong"].append(record.predicted_confidence)
                    stats["return_wrong"].append(record.actual_return or 0)
                
                # Track by direction
                if record.predicted_bias == "BULLISH":
                    stats["bullish_total"] += 1
                    if record.was_correct:
                        stats["bullish_correct"] += 1
                elif record.predicted_bias == "BEARISH":
                    stats["bearish_total"] += 1
                    if record.was_correct:
                        stats["bearish_correct"] += 1
            
            # Build accuracy objects
            accuracy_list = []
            for source, stats in source_stats.items():
                if stats["total"] > 0:
                    accuracy = SourceAccuracy(
                        source=SignalSourceType(source),
                        total_signals=stats["total"],
                        correct_predictions=stats["correct"],
                        accuracy=stats["correct"] / stats["total"],
                        avg_confidence_when_correct=sum(stats["conf_correct"]) / len(stats["conf_correct"]) if stats["conf_correct"] else 0,
                        avg_confidence_when_wrong=sum(stats["conf_wrong"]) / len(stats["conf_wrong"]) if stats["conf_wrong"] else 0,
                        avg_return_when_correct=sum(stats["return_correct"]) / len(stats["return_correct"]) if stats["return_correct"] else 0,
                        avg_return_when_wrong=sum(stats["return_wrong"]) / len(stats["return_wrong"]) if stats["return_wrong"] else 0,
                        bullish_accuracy=stats["bullish_correct"] / stats["bullish_total"] if stats["bullish_total"] > 0 else 0,
                        bearish_accuracy=stats["bearish_correct"] / stats["bearish_total"] if stats["bearish_total"] > 0 else 0,
                    )
                    accuracy_list.append(accuracy)
            
            # Sort by accuracy
            accuracy_list.sort(key=lambda x: x.accuracy, reverse=True)
            return accuracy_list
            
        except Exception as e:
            logger.error(f"Error getting accuracy ranking: {e}")
            return []
    
    async def record_prediction_outcome(
        self,
        prediction_id: str,
        ticker: str,
        source: str,
        predicted_bias: str,
        predicted_confidence: float,
        actual_return: float,
        resolution_price: float,
        holding_days: int = 5,
    ) -> None:
        """Record the outcome of a prediction for accuracy tracking."""
        try:
            # Determine if prediction was correct
            actual_direction = "UP" if actual_return > 0.02 else "DOWN" if actual_return < -0.02 else "FLAT"
            
            if predicted_bias == "BULLISH":
                was_correct = actual_direction == "UP"
            elif predicted_bias == "BEARISH":
                was_correct = actual_direction == "DOWN"
            else:
                was_correct = actual_direction == "FLAT"
            
            db = next(get_db())
            
            record = MiroFishAccuracyTracking(
                id=prediction_id,
                ticker=ticker,
                source=source,
                predicted_bias=predicted_bias,
                predicted_confidence=predicted_confidence,
                actual_return=actual_return,
                actual_direction=actual_direction,
                was_correct=was_correct,
                pnl_potential=actual_return * predicted_confidence,
                holding_days=holding_days,
                resolved_at=datetime.now(timezone.utc),
                resolution_price=resolution_price,
            )
            
            db.merge(record)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record prediction outcome: {e}")
    
    async def _store_comparison(self, comparison: ComprehensiveComparison) -> None:
        """Store comparison in database."""
        try:
            db = next(get_db())
            
            mirofish_signal = comparison.signals.get("mirofish", {})
            technical_signal = comparison.signals.get("technical", {})
            
            record = MiroFishComparison(
                id=comparison.id,
                ticker=comparison.ticker,
                mirofish_bias=mirofish_signal.get("bias", "NEUTRAL"),
                mirofish_confidence=mirofish_signal.get("confidence", 0),
                technical_bias=technical_signal.get("bias"),
                technical_confidence=technical_signal.get("confidence"),
                market_regime=comparison.signals.get("market_regime", {}).get("regime"),
                agreement_score=comparison.overall_agreement_score,
                disagreement_count=len(comparison.disagreements),
                comparison_data={c.source_1.value + "_vs_" + c.source_2.value: c.to_dict() for c in comparison.comparisons},
                timeframe=comparison.timeframe,
                metadata=comparison.metadata,
            )
            
            db.merge(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store comparison: {e}")


# Singleton instance
_comparator: SignalComparator | None = None


def get_comparator() -> SignalComparator:
    """Get or create the singleton comparator instance."""
    global _comparator
    if _comparator is None:
        _comparator = SignalComparator()
    return _comparator


async def compare_signals(
    ticker: str,
    timeframe: str = "5m",
    include_sources: list[str] | None = None,
) -> dict:
    """Convenience function to compare signals."""
    comparator = get_comparator()
    comparison = await comparator.compare_signals(
        ticker=ticker,
        timeframe=timeframe,
        include_sources=include_sources,
    )
    return comparison.to_dict()


async def get_accuracy_ranking(ticker: str) -> list[dict]:
    """Convenience function to get accuracy ranking."""
    comparator = get_comparator()
    rankings = await comparator._get_accuracy_ranking(ticker)
    return [r.to_dict() for r in rankings]


async def record_prediction_outcome(
    prediction_id: str,
    ticker: str,
    source: str,
    predicted_bias: str,
    predicted_confidence: float,
    actual_return: float,
    resolution_price: float,
    holding_days: int = 5,
) -> None:
    """Convenience function to record prediction outcome."""
    comparator = get_comparator()
    await comparator.record_prediction_outcome(
        prediction_id=prediction_id,
        ticker=ticker,
        source=source,
        predicted_bias=predicted_bias,
        predicted_confidence=predicted_confidence,
        actual_return=actual_return,
        resolution_price=resolution_price,
        holding_days=holding_days,
    )
