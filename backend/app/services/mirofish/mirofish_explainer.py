"""
MiroFish Explainer - Explainability and prediction breakdown.

Provides:
- Break down prediction components
- Weight of each factor (trend, momentum, sentiment, etc.)
- Key drivers identification
- Confidence breakdown by component
- Contradicting signals detection
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import Column, String, Float, DateTime, JSON, Integer, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.database import Base, get_db
from app.services.mirofish.mirofish_fleet import DirectionalBias, get_fleet
from app.services.mirofish.mirofish_ensemble import SignalSource, Action

logger = logging.getLogger(__name__)


# Database Models
class MiroFishExplanation(Base):
    """Database model for storing prediction explanations."""
    __tablename__ = "mirofish_explanations"
    
    id = Column(String(36), primary_key=True)
    prediction_id = Column(String(36), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Overall prediction
    overall_bias = Column(String(20), nullable=False)
    overall_confidence = Column(Float, nullable=False)
    
    # Component breakdown (stored as JSON)
    components = Column(JSON, default=dict)
    factor_weights = Column(JSON, default=dict)
    key_drivers = Column(JSON, default=list)
    confidence_breakdown = Column(JSON, default=dict)
    contradicting_signals = Column(JSON, default=list)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    lens = Column(String(50), nullable=True)
    metadata = Column(JSON, default=dict)


class MiroFishExplanationHistory(Base):
    """Database model for tracking explanation history."""
    __tablename__ = "mirofish_explanation_history"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Historical tracking
    prediction_id = Column(String(36), nullable=False)
    explanation_id = Column(String(36), nullable=False)
    accuracy = Column(Float, nullable=True)  # Actual outcome accuracy
    pnl_outcome = Column(Float, nullable=True)  # Actual P&L


class FactorType(Enum):
    """Types of factors in prediction."""
    TREND = "trend"
    MOMENTUM = "momentum"
    SENTIMENT = "sentiment"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    CATALYST = "catalyst"
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    MARKET_STRUCTURE = "market_structure"
    MACRO = "macro"
    NEWS = "news"
    RISK = "risk"


class SignalStrength(Enum):
    """Signal strength classification."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEUTRAL = "neutral"
    CONFLICTING = "conflicting"


@dataclass
class FactorComponent:
    """Individual factor component in prediction."""
    factor_type: FactorType
    weight: float  # 0-1 weight in final prediction
    contribution: float  # -1 to 1, negative = bearish contribution
    confidence: float  # 0-1 confidence in this factor
    raw_value: float | None = None  # Raw indicator value
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            "factor_type": self.factor_type.value,
            "weight": round(self.weight, 4),
            "contribution": round(self.contribution, 4),
            "confidence": round(self.confidence, 4),
            "raw_value": self.raw_value,
            "description": self.description,
            "signal_strength": self.classify_strength(),
        }
    
    def classify_strength(self) -> str:
        """Classify the signal strength."""
        abs_contrib = abs(self.contribution)
        if abs_contrib >= 0.7 and self.confidence >= 0.7:
            return SignalStrength.STRONG.value
        elif abs_contrib >= 0.4 and self.confidence >= 0.5:
            return SignalStrength.MODERATE.value
        elif abs_contrib >= 0.2:
            return SignalStrength.WEAK.value
        elif self.contribution == 0:
            return SignalStrength.NEUTRAL.value
        else:
            return SignalStrength.CONFLICTING.value


@dataclass
class ContradictingSignal:
    """Represents contradicting signals in analysis."""
    factor_1: FactorType
    factor_2: FactorType
    signal_1: str  # BULLISH/BEARISH/NEUTRAL
    signal_2: str
    severity: str  # high/medium/low
    explanation: str
    
    def to_dict(self) -> dict:
        return {
            "factor_1": self.factor_1.value,
            "factor_2": self.factor_2.value,
            "signal_1": self.signal_1,
            "signal_2": self.signal_2,
            "severity": self.severity,
            "explanation": self.explanation,
        }


@dataclass
class PredictionExplanation:
    """Complete explanation of a prediction."""
    prediction_id: str
    ticker: str
    timestamp: datetime
    
    # Overall
    overall_bias: DirectionalBias
    overall_confidence: float
    
    # Components
    components: list[FactorComponent] = field(default_factory=list)
    
    # Analysis
    key_drivers: list[dict] = field(default_factory=list)
    contradicting_signals: list[ContradictingSignal] = field(default_factory=list)
    
    # Metadata
    timeframe: str = "5m"
    lens: str = "overall"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "overall_bias": self.overall_bias.value,
            "overall_confidence": round(self.overall_confidence, 4),
            "timeframe": self.timeframe,
            "lens": self.lens,
            "components": [c.to_dict() for c in self.components],
            "factor_weights": self.get_factor_weights(),
            "key_drivers": self.key_drivers,
            "confidence_breakdown": self.get_confidence_breakdown(),
            "contradicting_signals": [c.to_dict() for c in self.contradicting_signals],
            "summary": self.generate_summary(),
            "metadata": self.metadata,
        }
    
    def get_factor_weights(self) -> dict:
        """Get weights of each factor type."""
        weights = {}
        for component in self.components:
            weights[component.factor_type.value] = round(component.weight, 4)
        return weights
    
    def get_confidence_breakdown(self) -> dict:
        """Get confidence breakdown by component."""
        breakdown = {}
        for component in self.components:
            breakdown[component.factor_type.value] = {
                "confidence": round(component.confidence, 4),
                "contribution": round(component.contribution, 4),
                "weighted_impact": round(component.confidence * abs(component.contribution), 4),
            }
        return breakdown
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        top_drivers = self.key_drivers[:3] if self.key_drivers else []
        driver_text = ", ".join([d.get("factor", "unknown") for d in top_drivers])
        
        conflict_count = len(self.contradicting_signals)
        conflict_text = f" with {conflict_count} contradicting signals" if conflict_count > 0 else ""
        
        return (
            f"{self.overall_bias.value} prediction for {self.ticker} "
            f"with {self.overall_confidence:.0%} confidence. "
            f"Key drivers: {driver_text}{conflict_text}."
        )


class PredictionExplainer:
    """
    Explains MiroFish predictions by breaking down components.
    
    Features:
    - Decompose predictions into factor contributions
    - Identify key drivers
    - Detect contradicting signals
    - Provide confidence breakdown
    """
    
    # Default factor weights (can be adjusted based on market regime)
    DEFAULT_FACTOR_WEIGHTS = {
        FactorType.TREND: 0.25,
        FactorType.MOMENTUM: 0.20,
        FactorType.SENTIMENT: 0.15,
        FactorType.VOLATILITY: 0.10,
        FactorType.VOLUME: 0.10,
        FactorType.CATALYST: 0.10,
        FactorType.FUNDAMENTAL: 0.05,
        FactorType.TECHNICAL: 0.05,
    }
    
    # Market regime adjustments
    REGIME_ADJUSTMENTS = {
        "bull": {
            FactorType.TREND: 1.2,
            FactorType.MOMENTUM: 1.1,
            FactorType.SENTIMENT: 1.3,
        },
        "bear": {
            FactorType.TREND: 1.2,
            FactorType.SENTIMENT: 0.8,
            FactorType.FUNDAMENTAL: 0.9,
        },
        "range": {
            FactorType.TREND: 0.8,
            FactorType.TECHNICAL: 1.3,
            FactorType.VOLATILITY: 1.2,
        },
    }
    
    def __init__(self):
        self.factor_weights = self.DEFAULT_FACTOR_WEIGHTS.copy()
    
    async def explain_prediction(
        self,
        prediction_id: str,
        ticker: str,
        raw_prediction: dict,
        timeframe: str = "5m",
        lens: str = "overall",
        market_regime: str | None = None,
    ) -> PredictionExplanation:
        """
        Generate explanation for a prediction.
        
        Args:
            prediction_id: Unique prediction identifier
            ticker: Stock symbol
            raw_prediction: Raw prediction data from MiroFish
            timeframe: Analysis timeframe
            lens: Analysis lens
            market_regime: Optional market regime for weight adjustment
            
        Returns:
            PredictionExplanation with full breakdown
        """
        # Adjust weights for market regime
        weights = self._adjust_weights_for_regime(market_regime)
        
        # Extract components from prediction
        components = self._extract_components(raw_prediction, weights)
        
        # Identify key drivers
        key_drivers = self._identify_key_drivers(components)
        
        # Detect contradicting signals
        contradicting = self._detect_contradictions(components)
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(components)
        
        # Determine overall bias
        overall_bias = self._calculate_overall_bias(components)
        
        explanation = PredictionExplanation(
            prediction_id=prediction_id,
            ticker=ticker.upper(),
            timestamp=datetime.now(timezone.utc),
            overall_bias=overall_bias,
            overall_confidence=overall_confidence,
            components=components,
            key_drivers=key_drivers,
            contradicting_signals=contradicting,
            timeframe=timeframe,
            lens=lens,
            metadata={
                "market_regime": market_regime,
                "raw_prediction": raw_prediction,
            },
        )
        
        # Store in database
        await self._store_explanation(explanation)
        
        return explanation
    
    def _adjust_weights_for_regime(self, regime: str | None) -> dict[FactorType, float]:
        """Adjust factor weights based on market regime."""
        weights = self.factor_weights.copy()
        
        if not regime:
            return weights
        
        adjustments = self.REGIME_ADJUSTMENTS.get(regime.lower(), {})
        
        for factor, multiplier in adjustments.items():
            if factor in weights:
                weights[factor] *= multiplier
        
        # Normalize to sum to 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _extract_components(
        self,
        raw_prediction: dict,
        weights: dict[FactorType, float],
    ) -> list[FactorComponent]:
        """Extract factor components from raw prediction."""
        components = []
        
        # Extract from different possible sources
        analyses = raw_prediction.get("analyses", [])
        
        if analyses:
            # Multi-analysis prediction (deep swarm)
            for analysis in analyses:
                component = self._analysis_to_component(analysis, weights)
                if component:
                    components.append(component)
        else:
            # Single prediction
            component = self._single_prediction_to_component(raw_prediction, weights)
            if component:
                components.append(component)
        
        # Add derived factors
        components.extend(self._derive_technical_factors(raw_prediction, weights))
        components.extend(self._derive_sentiment_factors(raw_prediction, weights))
        components.extend(self._derive_risk_factors(raw_prediction, weights))
        
        return components
    
    def _analysis_to_component(
        self,
        analysis: dict,
        weights: dict[FactorType, float],
    ) -> FactorComponent | None:
        """Convert a single analysis to factor component."""
        lens = analysis.get("lens", "overall")
        bias = analysis.get("bias", "NEUTRAL")
        confidence = analysis.get("confidence", 0.5)
        
        # Map lens to factor type
        factor_type = self._lens_to_factor_type(lens)
        weight = weights.get(factor_type, 0.1)
        
        # Convert bias to contribution
        contribution = self._bias_to_contribution(bias, confidence)
        
        return FactorComponent(
            factor_type=factor_type,
            weight=weight,
            contribution=contribution,
            confidence=confidence,
            description=analysis.get("summary", ""),
        )
    
    def _single_prediction_to_component(
        self,
        prediction: dict,
        weights: dict[FactorType, float],
    ) -> FactorComponent | None:
        """Convert single prediction to factor component."""
        bias = prediction.get("directional_bias", "NEUTRAL")
        confidence = prediction.get("confidence", 0.5)
        
        contribution = self._bias_to_contribution(bias, confidence)
        
        return FactorComponent(
            factor_type=FactorType.OVERALL,
            weight=1.0,
            contribution=contribution,
            confidence=confidence,
            description=prediction.get("scenario_summary", ""),
        )
    
    def _derive_technical_factors(
        self,
        raw_prediction: dict,
        weights: dict[FactorType, float],
    ) -> list[FactorComponent]:
        """Derive technical analysis factors."""
        factors = []
        
        # Check for technical indicators in risk flags or metadata
        risk_flags = raw_prediction.get("risk_flags", [])
        
        # Look for technical patterns
        technical_keywords = ["support", "resistance", "breakout", "breakdown", "pattern"]
        has_technical_signal = any(
            keyword in str(risk_flags).lower() 
            for keyword in technical_keywords
        )
        
        if has_technical_signal:
            # Estimate contribution based on context
            bias = raw_prediction.get("directional_bias", "NEUTRAL")
            confidence = 0.6  # Moderate confidence for derived factor
            
            factors.append(FactorComponent(
                factor_type=FactorType.TECHNICAL,
                weight=weights.get(FactorType.TECHNICAL, 0.05),
                contribution=self._bias_to_contribution(bias, confidence),
                confidence=confidence,
                description="Technical pattern detected in risk assessment",
            ))
        
        return factors
    
    def _derive_sentiment_factors(
        self,
        raw_prediction: dict,
        weights: dict[FactorType, float],
    ) -> list[FactorComponent]:
        """Derive sentiment factors."""
        factors = []
        
        catalyst = raw_prediction.get("catalyst_summary", "")
        scenario = raw_prediction.get("scenario_summary", "")
        
        # Look for sentiment indicators
        sentiment_keywords = ["sentiment", "mood", "attitude", "outlook", "consensus"]
        has_sentiment_signal = any(
            keyword in (catalyst + scenario).lower()
            for keyword in sentiment_keywords
        )
        
        if has_sentiment_signal:
            bias = raw_prediction.get("directional_bias", "NEUTRAL")
            confidence = 0.55
            
            factors.append(FactorComponent(
                factor_type=FactorType.SENTIMENT,
                weight=weights.get(FactorType.SENTIMENT, 0.15),
                contribution=self._bias_to_contribution(bias, confidence),
                confidence=confidence,
                description="Sentiment factor derived from catalyst/scenario",
            ))
        
        return factors
    
    def _derive_risk_factors(
        self,
        raw_prediction: dict,
        weights: dict[FactorType, float],
    ) -> list[FactorComponent]:
        """Derive risk factors."""
        factors = []
        
        risk_flags = raw_prediction.get("risk_flags", [])
        
        if risk_flags:
            # Risk flags generally reduce confidence
            risk_penalty = min(len(risk_flags) * 0.1, 0.3)
            confidence = max(0.5 - risk_penalty, 0.2)
            
            factors.append(FactorComponent(
                factor_type=FactorType.RISK,
                weight=weights.get(FactorType.RISK, 0.1),
                contribution=-risk_penalty,  # Risk is generally negative contribution
                confidence=confidence,
                description=f"Risk factors: {', '.join(risk_flags[:3])}",
            ))
        
        return factors
    
    def _lens_to_factor_type(self, lens: str) -> FactorType:
        """Map analysis lens to factor type."""
        lens_map = {
            "trend": FactorType.TREND,
            "momentum": FactorType.MOMENTUM,
            "sentiment": FactorType.SENTIMENT,
            "volatility": FactorType.VOLATILITY,
            "catalyst": FactorType.CATALYST,
            "fundamental": FactorType.FUNDAMENTAL,
            "technical": FactorType.TECHNICAL,
            "risk": FactorType.RISK,
            "overall": FactorType.TREND,
        }
        return lens_map.get(lens.lower(), FactorType.TECHNICAL)
    
    def _bias_to_contribution(self, bias: str, confidence: float) -> float:
        """Convert bias to contribution value (-1 to 1)."""
        bias_upper = bias.upper()
        if bias_upper == "BULLISH":
            return confidence
        elif bias_upper == "BEARISH":
            return -confidence
        else:
            return 0.0
    
    def _identify_key_drivers(self, components: list[FactorComponent]) -> list[dict]:
        """Identify the key drivers of the prediction."""
        # Sort by weighted impact (weight * |contribution|)
        sorted_components = sorted(
            components,
            key=lambda c: c.weight * abs(c.contribution),
            reverse=True,
        )
        
        drivers = []
        for component in sorted_components[:5]:  # Top 5 drivers
            impact = component.weight * abs(component.contribution)
            drivers.append({
                "factor": component.factor_type.value,
                "impact": round(impact, 4),
                "direction": "bullish" if component.contribution > 0 else "bearish" if component.contribution < 0 else "neutral",
                "confidence": round(component.confidence, 4),
                "description": component.description[:200] if component.description else "",
            })
        
        return drivers
    
    def _detect_contradictions(
        self,
        components: list[FactorComponent],
    ) -> list[ContradictingSignal]:
        """Detect contradicting signals between factors."""
        contradictions = []
        
        # Group by direction
        bullish_factors = [c for c in components if c.contribution > 0.3]
        bearish_factors = [c for c in components if c.contribution < -0.3]
        
        # Check for strong contradictions
        for bull in bullish_factors:
            for bear in bearish_factors:
                # Only flag if both have reasonable confidence
                if bull.confidence >= 0.5 and bear.confidence >= 0.5:
                    severity = "high" if (bull.confidence >= 0.7 and bear.confidence >= 0.7) else "medium"
                    
                    contradictions.append(ContradictingSignal(
                        factor_1=bull.factor_type,
                        factor_2=bear.factor_type,
                        signal_1="BULLISH",
                        signal_2="BEARISH",
                        severity=severity,
                        explanation=(
                            f"{bull.factor_type.value} suggests bullish ({bull.contribution:.2f}) "
                            f"but {bear.factor_type.value} suggests bearish ({bear.contribution:.2f})"
                        ),
                    ))
        
        return contradictions
    
    def _calculate_overall_confidence(self, components: list[FactorComponent]) -> float:
        """Calculate overall confidence from components."""
        if not components:
            return 0.5
        
        # Weighted average of component confidences
        total_weight = sum(c.weight for c in components)
        if total_weight == 0:
            return 0.5
        
        weighted_conf = sum(c.confidence * c.weight for c in components) / total_weight
        
        # Adjust for contradictions
        bullish_count = sum(1 for c in components if c.contribution > 0.2)
        bearish_count = sum(1 for c in components if c.contribution < -0.2)
        
        if bullish_count > 0 and bearish_count > 0:
            # Reduce confidence when there are conflicting signals
            conflict_ratio = min(bullish_count, bearish_count) / max(bullish_count, bearish_count, 1)
            weighted_conf *= (1 - conflict_ratio * 0.3)
        
        return round(max(0.0, min(1.0, weighted_conf)), 4)
    
    def _calculate_overall_bias(self, components: list[FactorComponent]) -> DirectionalBias:
        """Calculate overall bias from components."""
        if not components:
            return DirectionalBias.NEUTRAL
        
        # Calculate weighted sum
        total_weight = sum(c.weight for c in components)
        if total_weight == 0:
            return DirectionalBias.NEUTRAL
        
        weighted_sum = sum(c.contribution * c.weight for c in components) / total_weight
        
        if weighted_sum > 0.2:
            return DirectionalBias.BULLISH
        elif weighted_sum < -0.2:
            return DirectionalBias.BEARISH
        else:
            return DirectionalBias.NEUTRAL
    
    async def _store_explanation(self, explanation: PredictionExplanation) -> None:
        """Store explanation in database."""
        try:
            db = next(get_db())
            
            record = MiroFishExplanation(
                id=explanation.prediction_id,
                prediction_id=explanation.prediction_id,
                ticker=explanation.ticker,
                timestamp=explanation.timestamp,
                overall_bias=explanation.overall_bias.value,
                overall_confidence=explanation.overall_confidence,
                components=[c.to_dict() for c in explanation.components],
                factor_weights=explanation.get_factor_weights(),
                key_drivers=explanation.key_drivers,
                confidence_breakdown=explanation.get_confidence_breakdown(),
                contradicting_signals=[c.to_dict() for c in explanation.contradicting_signals],
                timeframe=explanation.timeframe,
                lens=explanation.lens,
                metadata=explanation.metadata,
            )
            
            db.merge(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store explanation: {e}")
    
    async def get_explanation(self, prediction_id: str) -> PredictionExplanation | None:
        """Retrieve explanation from database."""
        try:
            db = next(get_db())
            record = db.query(MiroFishExplanation).filter(
                MiroFishExplanation.prediction_id == prediction_id
            ).first()
            
            if not record:
                return None
            
            # Reconstruct explanation
            components = [
                FactorComponent(
                    factor_type=FactorType(c["factor_type"]),
                    weight=c["weight"],
                    contribution=c["contribution"],
                    confidence=c["confidence"],
                    raw_value=c.get("raw_value"),
                    description=c.get("description", ""),
                )
                for c in record.components
            ]
            
            return PredictionExplanation(
                prediction_id=record.prediction_id,
                ticker=record.ticker,
                timestamp=record.timestamp,
                overall_bias=DirectionalBias(record.overall_bias),
                overall_confidence=record.overall_confidence,
                components=components,
                key_drivers=record.key_drivers,
                contradicting_signals=[
                    ContradictingSignal(
                        factor_1=FactorType(c["factor_1"]),
                        factor_2=FactorType(c["factor_2"]),
                        signal_1=c["signal_1"],
                        signal_2=c["signal_2"],
                        severity=c["severity"],
                        explanation=c["explanation"],
                    )
                    for c in record.contradicting_signals
                ],
                timeframe=record.timeframe or "5m",
                lens=record.lens or "overall",
                metadata=record.metadata or {},
            )
        except Exception as e:
            logger.error(f"Failed to retrieve explanation: {e}")
            return None


# Singleton instance
_explainer: PredictionExplainer | None = None


def get_explainer() -> PredictionExplainer:
    """Get or create the singleton explainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = PredictionExplainer()
    return _explainer


async def explain_prediction(
    prediction_id: str,
    ticker: str,
    raw_prediction: dict,
    timeframe: str = "5m",
    lens: str = "overall",
    market_regime: str | None = None,
) -> dict:
    """Convenience function to explain a prediction."""
    explainer = get_explainer()
    explanation = await explainer.explain_prediction(
        prediction_id=prediction_id,
        ticker=ticker,
        raw_prediction=raw_prediction,
        timeframe=timeframe,
        lens=lens,
        market_regime=market_regime,
    )
    return explanation.to_dict()


async def get_explanation(prediction_id: str) -> dict | None:
    """Convenience function to retrieve an explanation."""
    explainer = get_explainer()
    explanation = await explainer.get_explanation(prediction_id)
    return explanation.to_dict() if explanation else None
