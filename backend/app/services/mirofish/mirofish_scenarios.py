"""
MiroFish Scenarios - Scenario analysis and what-if simulations.

Provides:
- What-if analysis (what if price moves X%?)
- Best case / worst case scenarios
- Probability distribution of outcomes
- Risk/reward analysis per signal
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from enum import Enum

from sqlalchemy import Column, String, Float, DateTime, JSON, Integer
from app.core.database import Base, get_db

from app.services.mirofish.mirofish_fleet import DirectionalBias, get_fleet
from app.services.mirofish_service import mirofish_predict

logger = logging.getLogger(__name__)


# Database Models
class MiroFishScenario(Base):
    """Database model for storing scenario analyses."""
    __tablename__ = "mirofish_scenarios"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Scenario parameters
    current_price = Column(Float, nullable=False)
    scenario_type = Column(String(50), nullable=False)  # what_if, best_case, worst_case, etc.
    
    # Results
    target_price = Column(Float, nullable=True)
    price_change_pct = Column(Float, nullable=True)
    probability = Column(Float, nullable=True)
    
    # Detailed results
    outcomes = Column(JSON, default=list)
    risk_reward = Column(JSON, default=dict)
    probability_distribution = Column(JSON, default=dict)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    prediction_metadata = Column(JSON, default=dict)


class ScenarioType(Enum):
    """Types of scenario analyses."""
    WHAT_IF = "what_if"
    BEST_CASE = "best_case"
    WORST_CASE = "worst_case"
    PROBABILITY_DIST = "probability_distribution"
    RISK_REWARD = "risk_reward"
    MONTE_CARLO = "monte_carlo"


class OutcomeLikelihood(Enum):
    """Likelihood classification for outcomes."""
    VERY_LIKELY = "very_likely"  # > 70%
    LIKELY = "likely"  # 50-70%
    POSSIBLE = "possible"  # 30-50%
    UNLIKELY = "unlikely"  # 10-30%
    VERY_UNLIKELY = "very_unlikely"  # < 10%


@dataclass
class ScenarioOutcome:
    """Individual scenario outcome."""
    price_target: float
    price_change_pct: float
    probability: float
    description: str
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    timeframe_days: int = 5
    
    def to_dict(self) -> dict:
        return {
            "price_target": round(self.price_target, 4),
            "price_change_pct": round(self.price_change_pct, 4),
            "probability": round(self.probability, 4),
            "likelihood": self.classify_likelihood(),
            "description": self.description,
            "catalysts": self.catalysts,
            "risks": self.risks,
            "timeframe_days": self.timeframe_days,
        }
    
    def classify_likelihood(self) -> str:
        """Classify the likelihood of this outcome."""
        if self.probability >= 0.7:
            return OutcomeLikelihood.VERY_LIKELY.value
        elif self.probability >= 0.5:
            return OutcomeLikelihood.LIKELY.value
        elif self.probability >= 0.3:
            return OutcomeLikelihood.POSSIBLE.value
        elif self.probability >= 0.1:
            return OutcomeLikelihood.UNLIKELY.value
        else:
            return OutcomeLikelihood.VERY_UNLIKELY.value


@dataclass
class RiskRewardAnalysis:
    """Risk/reward analysis for a signal."""
    entry_price: float
    target_price: float
    stop_loss: float
    
    # Calculated metrics
    potential_gain: float = field(init=False)
    potential_loss: float = field(init=False)
    risk_reward_ratio: float = field(init=False)
    break_even_probability: float = field(init=False)
    
    def __post_init__(self):
        self.potential_gain = self.target_price - self.entry_price
        self.potential_loss = self.entry_price - self.stop_loss
        self.risk_reward_ratio = (
            abs(self.potential_gain / self.potential_loss)
            if self.potential_loss != 0 else 0.0
        )
        # Minimum probability needed for positive expected value
        self.break_even_probability = (
            abs(self.potential_loss) / (abs(self.potential_gain) + abs(self.potential_loss))
            if (abs(self.potential_gain) + abs(self.potential_loss)) > 0 else 0.5
        )
    
    def to_dict(self) -> dict:
        return {
            "entry_price": round(self.entry_price, 4),
            "target_price": round(self.target_price, 4),
            "stop_loss": round(self.stop_loss, 4),
            "potential_gain": round(self.potential_gain, 4),
            "potential_loss": round(self.potential_loss, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "break_even_probability": round(self.break_even_probability, 4),
            "is_favorable": self.risk_reward_ratio >= 2.0,
        }


@dataclass
class ProbabilityDistribution:
    """Probability distribution of outcomes."""
    mean_return: float
    std_deviation: float
    skewness: float
    kurtosis: float
    
    # Percentile outcomes
    percentile_5: float
    percentile_25: float
    percentile_50: float  # Median
    percentile_75: float
    percentile_95: float
    
    # Probability of specific outcomes
    prob_positive: float
    prob_negative: float
    prob_large_gain: float  # > 10%
    prob_large_loss: float  # < -10%
    
    def to_dict(self) -> dict:
        return {
            "mean_return": round(self.mean_return, 4),
            "std_deviation": round(self.std_deviation, 4),
            "skewness": round(self.skewness, 4),
            "kurtosis": round(self.kurtosis, 4),
            "percentiles": {
                "5th": round(self.percentile_5, 4),
                "25th": round(self.percentile_25, 4),
                "50th": round(self.percentile_50, 4),
                "75th": round(self.percentile_75, 4),
                "95th": round(self.percentile_95, 4),
            },
            "probabilities": {
                "positive_return": round(self.prob_positive, 4),
                "negative_return": round(self.prob_negative, 4),
                "large_gain_10pct": round(self.prob_large_gain, 4),
                "large_loss_10pct": round(self.prob_large_loss, 4),
            },
        }


@dataclass
class ScenarioAnalysis:
    """Complete scenario analysis."""
    id: str
    ticker: str
    timestamp: datetime
    current_price: float
    
    # Scenarios
    what_if_scenarios: list[ScenarioOutcome] = field(default_factory=list)
    best_case: ScenarioOutcome | None = None
    worst_case: ScenarioOutcome | None = None
    expected_case: ScenarioOutcome | None = None
    
    # Analysis
    probability_distribution: ProbabilityDistribution | None = None
    risk_reward: RiskRewardAnalysis | None = None
    
    # Metadata
    timeframe: str = "5m"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "timestamp": self.timestamp.isoformat(),
            "current_price": round(self.current_price, 4),
            "timeframe": self.timeframe,
            "scenarios": {
                "what_if": [s.to_dict() for s in self.what_if_scenarios],
                "best_case": self.best_case.to_dict() if self.best_case else None,
                "worst_case": self.worst_case.to_dict() if self.worst_case else None,
                "expected_case": self.expected_case.to_dict() if self.expected_case else None,
            },
            "probability_distribution": self.probability_distribution.to_dict() if self.probability_distribution else None,
            "risk_reward": self.risk_reward.to_dict() if self.risk_reward else None,
            "summary": self.generate_summary(),
            "metadata": self.metadata,
        }
    
    def generate_summary(self) -> str:
        """Generate human-readable summary."""
        parts = []
        
        if self.best_case and self.worst_case:
            parts.append(
                f"Price range: ${self.worst_case.price_target:.2f} to ${self.best_case.price_target:.2f} "
                f"({self.worst_case.price_change_pct:+.1%} to {self.best_case.price_change_pct:+.1%})"
            )
        
        if self.risk_reward:
            parts.append(f"Risk/Reward: {self.risk_reward.risk_reward_ratio:.1f}:1")
        
        if self.probability_distribution:
            parts.append(
                f"Probability of positive return: {self.probability_distribution.prob_positive:.0%}"
            )
        
        return " | ".join(parts) if parts else "No scenario analysis available"


class ScenarioAnalyzer:
    """
    Analyzes scenarios and what-if situations for MiroFish predictions.
    
    Features:
    - What-if price movement analysis
    - Best/worst/expected case scenarios
    - Probability distribution estimation
    - Risk/reward calculation
    """
    
    # Scenario price movement ranges
    WHAT_IF_SCENARIOS = [-0.20, -0.10, -0.05, 0.05, 0.10, 0.20]
    
    # Volatility assumptions by timeframe
    VOLATILITY_BY_TIMEFRAME = {
        "1m": 0.02,   # 2% intraday
        "5m": 0.03,
        "15m": 0.04,
        "30m": 0.05,
        "1h": 0.06,
        "4h": 0.08,
        "1d": 0.12,   # 12% daily
        "1w": 0.25,   # 25% weekly
    }
    
    def __init__(self):
        self._scenario_cache: dict[str, ScenarioAnalysis] = {}
    
    async def analyze_scenarios(
        self,
        ticker: str,
        current_price: float,
        prediction: dict | None = None,
        timeframe: str = "5m",
        confidence_override: float | None = None,
    ) -> ScenarioAnalysis:
        """
        Run comprehensive scenario analysis.
        
        Args:
            ticker: Stock symbol
            current_price: Current market price
            prediction: Optional MiroFish prediction data
            timeframe: Analysis timeframe
            confidence_override: Optional confidence override
            
        Returns:
            ScenarioAnalysis with all scenarios
        """
        ticker = ticker.upper()
        scenario_id = f"{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        # Get prediction if not provided
        if not prediction:
            prediction = await mirofish_predict({
                "ticker": ticker,
                "timeframe": timeframe,
            })
        
        # Extract prediction data
        bias = prediction.get("directional_bias", "NEUTRAL")
        confidence = confidence_override or prediction.get("confidence", 0.5)
        
        # Generate what-if scenarios
        what_if = self._generate_what_if_scenarios(
            current_price, bias, confidence, timeframe
        )
        
        # Generate best/worst/expected cases
        best_case = self._generate_best_case(current_price, bias, confidence, timeframe)
        worst_case = self._generate_worst_case(current_price, bias, confidence, timeframe)
        expected_case = self._generate_expected_case(current_price, bias, confidence, timeframe)
        
        # Generate probability distribution
        prob_dist = self._estimate_probability_distribution(
            current_price, bias, confidence, timeframe
        )
        
        # Calculate risk/reward
        risk_reward = self._calculate_risk_reward(
            current_price, bias, confidence, prediction
        )
        
        analysis = ScenarioAnalysis(
            id=scenario_id,
            ticker=ticker,
            timestamp=datetime.now(timezone.utc),
            current_price=current_price,
            what_if_scenarios=what_if,
            best_case=best_case,
            worst_case=worst_case,
            expected_case=expected_case,
            probability_distribution=prob_dist,
            risk_reward=risk_reward,
            timeframe=timeframe,
            metadata={
                "prediction_bias": bias,
                "prediction_confidence": confidence,
                "volatility_assumption": self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05),
            },
        )
        
        # Store in database
        await self._store_scenario(analysis)
        
        return analysis
    
    def _generate_what_if_scenarios(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        timeframe: str,
    ) -> list[ScenarioOutcome]:
        """Generate what-if scenarios for different price movements."""
        scenarios = []
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        
        for price_change in self.WHAT_IF_SCENARIOS:
            target_price = current_price * (1 + price_change)
            
            # Calculate probability based on bias alignment and confidence
            bias_aligned = (
                (price_change > 0 and bias.upper() == "BULLISH") or
                (price_change < 0 and bias.upper() == "BEARISH")
            )
            
            if bias_aligned:
                base_prob = confidence * (1 - abs(price_change) / (volatility * 3))
            else:
                base_prob = (1 - confidence) * (1 - abs(price_change) / (volatility * 3))
            
            probability = max(0.05, min(0.95, base_prob))
            
            description = self._generate_scenario_description(
                price_change, bias, probability
            )
            
            scenarios.append(ScenarioOutcome(
                price_target=target_price,
                price_change_pct=price_change,
                probability=probability,
                description=description,
                catalysts=self._infer_catalysts(price_change, bias),
                risks=self._infer_risks(price_change, bias),
                timeframe_days=self._timeframe_to_days(timeframe),
            ))
        
        return sorted(scenarios, key=lambda s: s.price_change_pct)
    
    def _generate_best_case(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        timeframe: str,
    ) -> ScenarioOutcome:
        """Generate best case scenario."""
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        
        if bias.upper() == "BULLISH":
            price_change = volatility * 2.5 * confidence
        elif bias.upper() == "BEARISH":
            price_change = volatility * 0.5 * (1 - confidence)
        else:
            price_change = volatility * 1.5
        
        target_price = current_price * (1 + price_change)
        probability = confidence * 0.3  # Best case is less likely
        
        return ScenarioOutcome(
            price_target=target_price,
            price_change_pct=price_change,
            probability=max(0.1, min(0.4, probability)),
            description=f"Best case: All catalysts align in favor",
            catalysts=["Strong earnings", "Positive news flow", "Technical breakout"],
            risks=["Profit taking", "Unexpected macro events"],
            timeframe_days=self._timeframe_to_days(timeframe),
        )
    
    def _generate_worst_case(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        timeframe: str,
    ) -> ScenarioOutcome:
        """Generate worst case scenario."""
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        
        if bias.upper() == "BEARISH":
            price_change = -volatility * 2.5 * confidence
        elif bias.upper() == "BULLISH":
            price_change = -volatility * 0.5 * (1 - confidence)
        else:
            price_change = -volatility * 1.5
        
        target_price = current_price * (1 + price_change)
        probability = (1 - confidence) * 0.3 if bias.upper() != "BEARISH" else confidence * 0.3
        
        return ScenarioOutcome(
            price_target=target_price,
            price_change_pct=price_change,
            probability=max(0.1, min(0.4, probability)),
            description=f"Worst case: Key risks materialize",
            catalysts=[],
            risks=["Earnings miss", "Negative guidance", "Macro shock", "Technical breakdown"],
            timeframe_days=self._timeframe_to_days(timeframe),
        )
    
    def _generate_expected_case(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        timeframe: str,
    ) -> ScenarioOutcome:
        """Generate expected (base) case scenario."""
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        
        if bias.upper() == "BULLISH":
            price_change = volatility * confidence
        elif bias.upper() == "BEARISH":
            price_change = -volatility * confidence
        else:
            price_change = 0.0
        
        target_price = current_price * (1 + price_change)
        
        return ScenarioOutcome(
            price_target=target_price,
            price_change_pct=price_change,
            probability=confidence,
            description=f"Expected case based on current bias and confidence",
            catalysts=["Base case catalysts materialize"],
            risks=["Normal market volatility"],
            timeframe_days=self._timeframe_to_days(timeframe),
        )
    
    def _estimate_probability_distribution(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        timeframe: str,
    ) -> ProbabilityDistribution:
        """Estimate probability distribution of returns."""
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        
        # Adjust mean based on bias
        if bias.upper() == "BULLISH":
            mean_return = volatility * confidence * 0.5
            skewness = 0.3  # Positive skew for bullish bias
        elif bias.upper() == "BEARISH":
            mean_return = -volatility * confidence * 0.5
            skewness = -0.3  # Negative skew for bearish bias
        else:
            mean_return = 0.0
            skewness = 0.0
        
        # Standard deviation scales with volatility
        std_dev = volatility * (1.5 - confidence * 0.5)  # Higher confidence = lower uncertainty
        
        # Calculate percentiles (assuming normal distribution with skew)
        percentile_5 = mean_return + std_dev * (-1.645 + skewness * 0.3)
        percentile_25 = mean_return + std_dev * (-0.674 + skewness * 0.2)
        percentile_50 = mean_return + std_dev * (0 + skewness * 0.1)
        percentile_75 = mean_return + std_dev * (0.674 + skewness * 0.2)
        percentile_95 = mean_return + std_dev * (1.645 + skewness * 0.3)
        
        # Calculate probabilities
        from math import erf, sqrt
        
        def normal_cdf(x):
            return 0.5 * (1 + erf(x / sqrt(2)))
        
        prob_positive = 1 - normal_cdf(-mean_return / std_dev) if std_dev > 0 else 0.5
        prob_negative = 1 - prob_positive
        prob_large_gain = 1 - normal_cdf((0.10 - mean_return) / std_dev) if std_dev > 0 else 0.1
        prob_large_loss = normal_cdf((-0.10 - mean_return) / std_dev) if std_dev > 0 else 0.1
        
        return ProbabilityDistribution(
            mean_return=mean_return,
            std_deviation=std_dev,
            skewness=skewness,
            kurtosis=3.0,  # Normal distribution
            percentile_5=percentile_5,
            percentile_25=percentile_25,
            percentile_50=percentile_50,
            percentile_75=percentile_75,
            percentile_95=percentile_95,
            prob_positive=prob_positive,
            prob_negative=prob_negative,
            prob_large_gain=prob_large_gain,
            prob_large_loss=prob_large_loss,
        )
    
    def _calculate_risk_reward(
        self,
        current_price: float,
        bias: str,
        confidence: float,
        prediction: dict,
    ) -> RiskRewardAnalysis:
        """Calculate risk/reward for the signal."""
        volatility = 0.05  # Default 5%
        
        if bias.upper() == "BULLISH":
            target_price = current_price * (1 + volatility * 2 * confidence)
            stop_loss = current_price * (1 - volatility * confidence)
        elif bias.upper() == "BEARISH":
            target_price = current_price * (1 - volatility * 2 * confidence)
            stop_loss = current_price * (1 + volatility * confidence)
        else:
            # Neutral - symmetric
            target_price = current_price * 1.05
            stop_loss = current_price * 0.95
        
        return RiskRewardAnalysis(
            entry_price=current_price,
            target_price=target_price,
            stop_loss=stop_loss,
        )
    
    def _generate_scenario_description(
        self,
        price_change: float,
        bias: str,
        probability: float,
    ) -> str:
        """Generate human-readable scenario description."""
        direction = "up" if price_change > 0 else "down"
        magnitude = "sharply" if abs(price_change) > 0.1 else "moderately" if abs(price_change) > 0.05 else "slightly"
        
        bias_aligned = (
            (price_change > 0 and bias.upper() == "BULLISH") or
            (price_change < 0 and bias.upper() == "BEARISH")
        )
        
        alignment = "aligns with" if bias_aligned else "contradicts"
        
        return f"Price moves {magnitude} {direction} ({price_change:+.1%}), {alignment} current bias"
    
    def _infer_catalysts(self, price_change: float, bias: str) -> list[str]:
        """Infer potential catalysts for a scenario."""
        if price_change > 0.1:
            return ["Strong earnings beat", "Positive guidance", "Sector rotation", "Technical breakout"]
        elif price_change > 0:
            return ["Mild positive sentiment", "Market rally", "Sector strength"]
        elif price_change > -0.1:
            return ["Mild profit taking", "Market pullback", "Sector weakness"]
        else:
            return ["Earnings miss", "Negative guidance", "Macro shock", "Technical breakdown"]
    
    def _infer_risks(self, price_change: float, bias: str) -> list[str]:
        """Infer potential risks for a scenario."""
        if price_change > 0:
            return ["Profit taking", "Overbought conditions", "Unexpected negative news"]
        else:
            return ["Further downside", "Oversold conditions", "Capitulation selling"]
    
    def _timeframe_to_days(self, timeframe: str) -> int:
        """Convert timeframe to approximate days."""
        mapping = {
            "1m": 1,
            "5m": 1,
            "15m": 1,
            "30m": 1,
            "1h": 1,
            "4h": 1,
            "1d": 5,
            "1w": 21,
        }
        return mapping.get(timeframe, 5)
    
    async def run_monte_carlo(
        self,
        ticker: str,
        current_price: float,
        num_simulations: int = 1000,
        timeframe: str = "5m",
    ) -> dict:
        """
        Run Monte Carlo simulation for price paths.
        
        Args:
            ticker: Stock symbol
            current_price: Starting price
            num_simulations: Number of simulation runs
            timeframe: Analysis timeframe
            
        Returns:
            Dictionary with simulation results
        """
        volatility = self.VOLATILITY_BY_TIMEFRAME.get(timeframe, 0.05)
        days = self._timeframe_to_days(timeframe)
        
        # Get prediction for drift
        prediction = await mirofish_predict({"ticker": ticker, "timeframe": timeframe})
        bias = prediction.get("directional_bias", "NEUTRAL")
        confidence = prediction.get("confidence", 0.5)
        
        # Calculate drift
        if bias.upper() == "BULLISH":
            drift = volatility * confidence * 0.1
        elif bias.upper() == "BEARISH":
            drift = -volatility * confidence * 0.1
        else:
            drift = 0.0
        
        # Run simulations
        final_prices = []
        for _ in range(num_simulations):
            price = current_price
            for _ in range(days):
                # Geometric Brownian Motion
                daily_return = random.gauss(drift, volatility / sqrt(days))
                price *= (1 + daily_return)
            final_prices.append(price)
        
        # Calculate statistics
        final_prices.sort()
        returns = [(p / current_price) - 1 for p in final_prices]
        
        mean_return = sum(returns) / len(returns)
        std_dev = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
        
        return {
            "ticker": ticker,
            "current_price": round(current_price, 4),
            "num_simulations": num_simulations,
            "timeframe": timeframe,
            "statistics": {
                "mean_return": round(mean_return, 4),
                "std_deviation": round(std_dev, 4),
                "min_return": round(min(returns), 4),
                "max_return": round(max(returns), 4),
            },
            "percentiles": {
                "1st": round(final_prices[int(num_simulations * 0.01)], 4),
                "5th": round(final_prices[int(num_simulations * 0.05)], 4),
                "25th": round(final_prices[int(num_simulations * 0.25)], 4),
                "50th": round(final_prices[int(num_simulations * 0.50)], 4),
                "75th": round(final_prices[int(num_simulations * 0.75)], 4),
                "95th": round(final_prices[int(num_simulations * 0.95)], 4),
                "99th": round(final_prices[int(num_simulations * 0.99)], 4),
            },
            "probabilities": {
                "positive": round(sum(1 for r in returns if r > 0) / len(returns), 4),
                "negative": round(sum(1 for r in returns if r < 0) / len(returns), 4),
                "greater_than_10pct": round(sum(1 for r in returns if r > 0.10) / len(returns), 4),
                "less_than_minus10pct": round(sum(1 for r in returns if r < -0.10) / len(returns), 4),
            },
        }
    
    async def _store_scenario(self, analysis: ScenarioAnalysis) -> None:
        """Store scenario analysis in database."""
        try:
            db = next(get_db())
            
            record = MiroFishScenario(
                id=analysis.id,
                ticker=analysis.ticker,
                timestamp=analysis.timestamp,
                current_price=analysis.current_price,
                scenario_type="comprehensive",
                outcomes=[s.to_dict() for s in analysis.what_if_scenarios],
                risk_reward=analysis.risk_reward.to_dict() if analysis.risk_reward else {},
                probability_distribution=analysis.probability_distribution.to_dict() if analysis.probability_distribution else {},
                timeframe=analysis.timeframe,
                metadata=analysis.metadata,
            )
            
            db.merge(record)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to store scenario: {e}")


# Singleton instance
_analyzer: ScenarioAnalyzer | None = None


def get_scenario_analyzer() -> ScenarioAnalyzer:
    """Get or create the singleton scenario analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ScenarioAnalyzer()
    return _analyzer


async def analyze_scenarios(
    ticker: str,
    current_price: float,
    prediction: dict | None = None,
    timeframe: str = "5m",
) -> dict:
    """Convenience function for scenario analysis."""
    analyzer = get_scenario_analyzer()
    analysis = await analyzer.analyze_scenarios(
        ticker=ticker,
        current_price=current_price,
        prediction=prediction,
        timeframe=timeframe,
    )
    return analysis.to_dict()


async def run_monte_carlo(
    ticker: str,
    current_price: float,
    num_simulations: int = 1000,
    timeframe: str = "5m",
) -> dict:
    """Convenience function for Monte Carlo simulation."""
    analyzer = get_scenario_analyzer()
    return await analyzer.run_monte_carlo(
        ticker=ticker,
        current_price=current_price,
        num_simulations=num_simulations,
        timeframe=timeframe,
    )


# Import at end to avoid circular imports
from math import sqrt
