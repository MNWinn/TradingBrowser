"""
MiroFish Fleet - Multi-timeframe, multi-lens assessment management.

Manages multiple MiroFish assessments across timeframes and lenses,
aggregating confidence and detecting disagreements.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.services.focus_runtime import is_focus_ticker


class Timeframe(Enum):
    """Supported analysis timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class Lens(Enum):
    """Analysis lenses/perspectives."""
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    CATALYST = "catalyst"
    RISK = "risk"
    OVERALL = "overall"


class DirectionalBias(Enum):
    """Directional bias enumeration."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass
class MiroFishAssessment:
    """Single MiroFish assessment result."""
    ticker: str
    timeframe: str
    lens: str
    bias: DirectionalBias
    confidence: float
    summary: str | None = None
    catalyst: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    provider_mode: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: dict | None = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "lens": self.lens,
            "bias": self.bias.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "catalyst": self.catalyst,
            "risk_flags": self.risk_flags,
            "provider_mode": self.provider_mode,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FleetAnalysis:
    """Complete fleet analysis result."""
    ticker: str
    assessments: list[MiroFishAssessment] = field(default_factory=list)
    aggregated_bias: DirectionalBias = DirectionalBias.UNKNOWN
    aggregated_confidence: float = 0.0
    alignment_score: float = 0.0
    disagreement_score: float = 0.0
    timeframe_consensus: dict[str, Any] = field(default_factory=dict)
    lens_consensus: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "assessments": [a.to_dict() for a in self.assessments],
            "aggregated_bias": self.aggregated_bias.value,
            "aggregated_confidence": self.aggregated_confidence,
            "alignment_score": self.alignment_score,
            "disagreement_score": self.disagreement_score,
            "timeframe_consensus": self.timeframe_consensus,
            "lens_consensus": self.lens_consensus,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class DisagreementDetector:
    """Detects and analyzes disagreements across assessments."""

    @staticmethod
    def detect_timeframe_divergence(assessments: list[MiroFishAssessment]) -> dict:
        """
        Detect when different timeframes disagree significantly.
        
        Returns dict with:
        - has_divergence: bool
        - short_term_bias: DirectionalBias
        - long_term_bias: DirectionalBias
        - divergence_score: float (0-1)
        - explanation: str
        """
        short_timeframes = {"1m", "5m", "15m", "30m"}
        long_timeframes = {"1d", "1w", "4h"}

        short_assessments = [a for a in assessments if a.timeframe in short_timeframes]
        long_assessments = [a for a in assessments if a.timeframe in long_timeframes]

        if not short_assessments or not long_assessments:
            return {
                "has_divergence": False,
                "short_term_bias": DirectionalBias.UNKNOWN,
                "long_term_bias": DirectionalBias.UNKNOWN,
                "divergence_score": 0.0,
                "explanation": "Insufficient timeframe coverage for divergence detection",
            }

        short_bias = DisagreementDetector._majority_bias(short_assessments)
        long_bias = DisagreementDetector._majority_bias(long_assessments)

        short_conf = sum(a.confidence for a in short_assessments) / len(short_assessments)
        long_conf = sum(a.confidence for a in long_assessments) / len(long_assessments)

        has_divergence = short_bias != long_bias and short_bias != DirectionalBias.NEUTRAL and long_bias != DirectionalBias.NEUTRAL

        divergence_score = 0.0
        explanation = "Timeframes aligned"

        if has_divergence:
            divergence_score = (short_conf + long_conf) / 2
            explanation = f"Short-term ({short_bias.value}) diverges from long-term ({long_bias.value})"

        return {
            "has_divergence": has_divergence,
            "short_term_bias": short_bias,
            "long_term_bias": long_bias,
            "divergence_score": divergence_score,
            "explanation": explanation,
            "short_confidence": short_conf,
            "long_confidence": long_conf,
        }

    @staticmethod
    def detect_lens_conflicts(assessments: list[MiroFishAssessment]) -> list[dict]:
        """Detect conflicts between different analysis lenses."""
        conflicts = []

        lens_groups: dict[str, list[MiroFishAssessment]] = {}
        for a in assessments:
            lens_groups.setdefault(a.lens, []).append(a)

        lens_biases = {}
        for lens, lens_assessments in lens_groups.items():
            lens_biases[lens] = DisagreementDetector._majority_bias(lens_assessments)

        critical_lenses = ["technical", "fundamental", "sentiment"]
        for i, lens1 in enumerate(critical_lenses):
            for lens2 in critical_lenses[i+1:]:
                if lens1 in lens_biases and lens2 in lens_biases:
                    bias1 = lens_biases[lens1]
                    bias2 = lens_biases[lens2]

                    if bias1 != bias2 and bias1 != DirectionalBias.NEUTRAL and bias2 != DirectionalBias.NEUTRAL:
                        conflicts.append({
                            "lens_1": lens1,
                            "lens_2": lens2,
                            "bias_1": bias1.value,
                            "bias_2": bias2.value,
                            "severity": "high" if lens1 in ("technical", "fundamental") and lens2 in ("technical", "fundamental") else "medium",
                            "explanation": f"{lens1} suggests {bias1.value} but {lens2} suggests {bias2.value}",
                        })

        return conflicts

    @staticmethod
    def calculate_confidence_variance(assessments: list[MiroFishAssessment]) -> dict:
        """Calculate confidence variance across assessments."""
        if len(assessments) < 2:
            return {"variance": 0.0, "std_dev": 0.0, "range": 0.0}

        confidences = [a.confidence for a in assessments]
        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
        std_dev = variance ** 0.5

        return {
            "variance": round(variance, 4),
            "std_dev": round(std_dev, 4),
            "range": round(max(confidences) - min(confidences), 4),
            "mean": round(mean_conf, 4),
        }

    @staticmethod
    def _majority_bias(assessments: list[MiroFishAssessment]) -> DirectionalBias:
        """Get the majority bias from a list of assessments."""
        votes = {DirectionalBias.BULLISH: 0, DirectionalBias.BEARISH: 0, DirectionalBias.NEUTRAL: 0}

        for a in assessments:
            votes[a.bias] = votes.get(a.bias, 0) + 1

        return max(votes, key=votes.get)


class ConfidenceAggregator:
    """Aggregates confidence across multiple assessments."""

    @staticmethod
    def aggregate(assessments: list[MiroFishAssessment], method: str = "weighted") -> tuple[DirectionalBias, float]:
        """
        Aggregate assessments into a single bias and confidence.
        
        Methods:
        - simple: Simple majority vote
        - weighted: Weight by confidence
        - confidence_threshold: Only count high-confidence assessments
        - timeframe_weighted: Weight by timeframe significance
        """
        if not assessments:
            return DirectionalBias.UNKNOWN, 0.0

        if method == "simple":
            return ConfidenceAggregator._simple_vote(assessments)
        elif method == "weighted":
            return ConfidenceAggregator._weighted_vote(assessments)
        elif method == "confidence_threshold":
            return ConfidenceAggregator._threshold_vote(assessments, threshold=0.6)
        elif method == "timeframe_weighted":
            return ConfidenceAggregator._timeframe_weighted_vote(assessments)
        else:
            return ConfidenceAggregator._weighted_vote(assessments)

    @staticmethod
    def _simple_vote(assessments: list[MiroFishAssessment]) -> tuple[DirectionalBias, float]:
        """Simple majority vote."""
        votes = {DirectionalBias.BULLISH: 0, DirectionalBias.BEARISH: 0, DirectionalBias.NEUTRAL: 0}

        for a in assessments:
            votes[a.bias] = votes.get(a.bias, 0) + 1

        majority_bias = max(votes, key=votes.get)
        total = sum(votes.values())
        confidence = votes[majority_bias] / total if total > 0 else 0.0

        return majority_bias, round(confidence, 3)

    @staticmethod
    def _weighted_vote(assessments: list[MiroFishAssessment]) -> tuple[DirectionalBias, float]:
        """Weight votes by confidence."""
        weighted_votes = {DirectionalBias.BULLISH: 0.0, DirectionalBias.BEARISH: 0.0, DirectionalBias.NEUTRAL: 0.0}

        for a in assessments:
            weighted_votes[a.bias] += a.confidence

        majority_bias = max(weighted_votes, key=weighted_votes.get)
        total_weight = sum(weighted_votes.values())
        confidence = weighted_votes[majority_bias] / total_weight if total_weight > 0 else 0.0

        return majority_bias, round(confidence, 3)

    @staticmethod
    def _threshold_vote(assessments: list[MiroFishAssessment], threshold: float = 0.6) -> tuple[DirectionalBias, float]:
        """Only count assessments above confidence threshold."""
        high_conf = [a for a in assessments if a.confidence >= threshold]

        if not high_conf:
            return ConfidenceAggregator._weighted_vote(assessments)

        return ConfidenceAggregator._weighted_vote(high_conf)

    @staticmethod
    def _timeframe_weighted_vote(assessments: list[MiroFishAssessment]) -> tuple[DirectionalBias, float]:
        """Weight by timeframe significance."""
        timeframe_weights = {
            "1m": 0.5,
            "5m": 0.7,
            "15m": 0.8,
            "30m": 0.9,
            "1h": 1.0,
            "4h": 1.1,
            "1d": 1.2,
            "1w": 1.3,
        }

        weighted_votes = {DirectionalBias.BULLISH: 0.0, DirectionalBias.BEARISH: 0.0, DirectionalBias.NEUTRAL: 0.0}

        for a in assessments:
            weight = timeframe_weights.get(a.timeframe, 1.0)
            weighted_votes[a.bias] += a.confidence * weight

        majority_bias = max(weighted_votes, key=weighted_votes.get)
        total_weight = sum(weighted_votes.values())
        confidence = weighted_votes[majority_bias] / total_weight if total_weight > 0 else 0.0

        return majority_bias, round(confidence, 3)


class MiroFishFleet:
    """
    Manages multiple MiroFish assessments across timeframes and lenses.
    
    Provides:
    - Multi-timeframe analysis (1m, 5m, 15m, 1h, 1d, 1w)
    - Multiple lenses (technical, sentiment, fundamental)
    - Confidence aggregation across timeframes
    - Disagreement detection
    """

    DEFAULT_TIMEFRAMES = ["5m", "15m", "1h", "1d"]
    DEFAULT_LENSES = ["technical", "sentiment", "trend", "risk"]
    FOCUS_TIMEFRAMES = ["1m", "5m", "15m", "1h", "1d", "1w"]
    FOCUS_LENSES = ["technical", "sentiment", "fundamental", "trend", "momentum", "volatility", "catalyst", "risk"]

    def __init__(
        self,
        max_concurrent: int = 8,
        timeout_per_request: float = 6.0,
    ):
        self.max_concurrent = max_concurrent
        self.timeout_per_request = timeout_per_request
        self.confidence_aggregator = ConfidenceAggregator()
        self.disagreement_detector = DisagreementDetector()

    async def analyze(
        self,
        ticker: str,
        timeframes: list[str] | None = None,
        lenses: list[str] | None = None,
        aggregation_method: str = "weighted",
        include_raw: bool = False,
    ) -> FleetAnalysis:
        """
        Run comprehensive multi-timeframe, multi-lens analysis.
        
        Args:
            ticker: Stock symbol to analyze
            timeframes: List of timeframes to analyze (uses defaults if None)
            lenses: List of lenses to apply (uses defaults if None)
            aggregation_method: Method for aggregating results
            include_raw: Whether to include raw API responses
            
        Returns:
            FleetAnalysis with aggregated results and metadata
        """
        ticker = ticker.upper()
        focus = is_focus_ticker(ticker)

        if timeframes is None:
            timeframes = self.FOCUS_TIMEFRAMES if focus else self.DEFAULT_TIMEFRAMES
        if lenses is None:
            lenses = self.FOCUS_LENSES if focus else self.DEFAULT_LENSES

        focus_context = "priority watchlist ticker" if focus else ""

        assessments = await self._gather_assessments(
            ticker=ticker,
            timeframes=timeframes,
            lenses=lenses,
            focus_context=focus_context,
            include_raw=include_raw,
        )

        aggregated_bias, aggregated_confidence = self.confidence_aggregator.aggregate(
            assessments, method=aggregation_method
        )

        alignment_score = self._calculate_alignment(assessments)
        disagreement_score = 1.0 - alignment_score

        timeframe_consensus = self._analyze_timeframe_consensus(assessments)
        lens_consensus = self._analyze_lens_consensus(assessments)

        divergence = self.disagreement_detector.detect_timeframe_divergence(assessments)
        lens_conflicts = self.disagreement_detector.detect_lens_conflicts(assessments)
        confidence_variance = self.disagreement_detector.calculate_confidence_variance(assessments)

        return FleetAnalysis(
            ticker=ticker,
            assessments=assessments,
            aggregated_bias=aggregated_bias,
            aggregated_confidence=aggregated_confidence,
            alignment_score=alignment_score,
            disagreement_score=disagreement_score,
            timeframe_consensus=timeframe_consensus,
            lens_consensus=lens_consensus,
            metadata={
                "focus_ticker": focus,
                "aggregation_method": aggregation_method,
                "divergence": divergence,
                "lens_conflicts": lens_conflicts,
                "confidence_variance": confidence_variance,
                "total_assessments": len(assessments),
                "timeframes_analyzed": timeframes,
                "lenses_analyzed": lenses,
            },
        )

    async def quick_analysis(
        self,
        ticker: str,
        timeframes: list[str] | None = None,
    ) -> dict:
        """
        Quick single-lens analysis for rapid decision support.
        
        Uses only the 'overall' lens for speed.
        """
        timeframes = timeframes or ["5m", "15m", "1h"]
        result = await self.analyze(
            ticker=ticker,
            timeframes=timeframes,
            lenses=["overall"],
            aggregation_method="timeframe_weighted",
        )
        return result.to_dict()

    async def deep_analysis(
        self,
        ticker: str,
    ) -> FleetAnalysis:
        """
        Deep analysis with all timeframes and lenses.
        
        Best for focus tickers requiring comprehensive evaluation.
        """
        return await self.analyze(
            ticker=ticker,
            timeframes=self.FOCUS_TIMEFRAMES,
            lenses=self.FOCUS_LENSES,
            aggregation_method="timeframe_weighted",
            include_raw=True,
        )

    async def _gather_assessments(
        self,
        ticker: str,
        timeframes: list[str],
        lenses: list[str],
        focus_context: str,
        include_raw: bool,
    ) -> list[MiroFishAssessment]:
        """Gather assessments with concurrency control."""
        assessments: list[MiroFishAssessment] = []
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Import here to avoid circular imports
        from app.services.mirofish import mirofish_predict

        async def fetch_single(tf: str, lens: str) -> MiroFishAssessment | None:
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        mirofish_predict({
                            "ticker": ticker,
                            "timeframe": tf,
                            "lens": lens,
                            "focus_context": focus_context,
                            "objective": "fleet multi-timeframe analysis",
                        }),
                        timeout=self.timeout_per_request,
                    )

                    bias_str = result.get("directional_bias", "NEUTRAL").upper()
                    try:
                        bias = DirectionalBias(bias_str)
                    except ValueError:
                        bias = DirectionalBias.NEUTRAL

                    return MiroFishAssessment(
                        ticker=ticker,
                        timeframe=tf,
                        lens=lens,
                        bias=bias,
                        confidence=float(result.get("confidence", 0.5)),
                        summary=result.get("scenario_summary"),
                        catalyst=result.get("catalyst_summary"),
                        risk_flags=result.get("risk_flags", []),
                        provider_mode=result.get("provider_mode", "unknown"),
                        raw_response=result if include_raw else None,
                    )
                except asyncio.TimeoutError:
                    return MiroFishAssessment(
                        ticker=ticker,
                        timeframe=tf,
                        lens=lens,
                        bias=DirectionalBias.UNKNOWN,
                        confidence=0.0,
                        summary="Request timeout",
                        provider_mode="timeout",
                    )
                except Exception as e:
                    return MiroFishAssessment(
                        ticker=ticker,
                        timeframe=tf,
                        lens=lens,
                        bias=DirectionalBias.UNKNOWN,
                        confidence=0.0,
                        summary=f"Error: {str(e)}",
                        provider_mode="error",
                    )

        tasks = [fetch_single(tf, lens) for tf in timeframes for lens in lenses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, MiroFishAssessment):
                assessments.append(result)
            elif isinstance(result, Exception):
                assessments.append(MiroFishAssessment(
                    ticker=ticker,
                    timeframe="unknown",
                    lens="unknown",
                    bias=DirectionalBias.UNKNOWN,
                    confidence=0.0,
                    summary=f"Exception: {str(result)}",
                    provider_mode="exception",
                ))

        return assessments

    def _calculate_alignment(self, assessments: list[MiroFishAssessment]) -> float:
        """Calculate alignment score across assessments."""
        if not assessments:
            return 0.0

        votes = {}
        for a in assessments:
            votes[a.bias] = votes.get(a.bias, 0) + 1

        max_votes = max(votes.values()) if votes else 0
        return max_votes / len(assessments)

    def _analyze_timeframe_consensus(self, assessments: list[MiroFishAssessment]) -> dict:
        """Analyze consensus per timeframe."""
        timeframe_results: dict[str, list[MiroFishAssessment]] = {}
        for a in assessments:
            timeframe_results.setdefault(a.timeframe, []).append(a)

        consensus = {}
        for tf, tf_assessments in timeframe_results.items():
            bias, conf = self.confidence_aggregator.aggregate(tf_assessments, method="weighted")
            consensus[tf] = {
                "bias": bias.value,
                "confidence": conf,
                "assessments_count": len(tf_assessments),
            }

        return consensus

    def _analyze_lens_consensus(self, assessments: list[MiroFishAssessment]) -> dict:
        """Analyze consensus per lens."""
        lens_results: dict[str, list[MiroFishAssessment]] = {}
        for a in assessments:
            lens_results.setdefault(a.lens, []).append(a)

        consensus = {}
        for lens, lens_assessments in lens_results.items():
            bias, conf = self.confidence_aggregator.aggregate(lens_assessments, method="weighted")
            consensus[lens] = {
                "bias": bias.value,
                "confidence": conf,
                "assessments_count": len(lens_assessments),
            }

        return consensus


# Singleton instance
_fleet: MiroFishFleet | None = None


def get_fleet() -> MiroFishFleet:
    """Get or create the singleton fleet instance."""
    global _fleet
    if _fleet is None:
        _fleet = MiroFishFleet()
    return _fleet


async def fleet_analyze(
    ticker: str,
    timeframes: list[str] | None = None,
    lenses: list[str] | None = None,
    aggregation_method: str = "weighted",
) -> dict:
    """Convenience function for fleet analysis."""
    fleet = get_fleet()
    result = await fleet.analyze(
        ticker=ticker,
        timeframes=timeframes,
        lenses=lenses,
        aggregation_method=aggregation_method,
    )
    return result.to_dict()


async def fleet_quick(ticker: str, timeframes: list[str] | None = None) -> dict:
    """Convenience function for quick analysis."""
    fleet = get_fleet()
    return await fleet.quick_analysis(ticker, timeframes)


async def fleet_deep(ticker: str) -> dict:
    """Convenience function for deep analysis."""
    fleet = get_fleet()
    result = await fleet.deep_analysis(ticker)
    return result.to_dict()
