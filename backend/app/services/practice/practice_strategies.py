"""Practice Trading Strategies - Strategy implementations for paper trading.

This module provides various trading strategies including MiroFish-based,
technical indicator, multi-agent consensus, and a custom strategy builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable

import httpx

from app.core.config import settings
from app.services.mirofish_service import mirofish_predict, mirofish_deep_swarm
from app.services.market_data import MarketDataService


class StrategySignal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategyRecommendation:
    """A trading recommendation from a strategy."""
    
    ticker: str
    signal: StrategySignal
    confidence: float  # 0.0 to 1.0
    suggested_position_size: Decimal
    rationale: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_actionable(self) -> bool:
        """Check if this recommendation should trigger a trade."""
        return self.signal in (StrategySignal.BUY, StrategySignal.SELL) and self.confidence >= 0.5


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self._market_data = MarketDataService()
    
    @abstractmethod
    async def analyze(self, ticker: str, context: dict[str, Any] | None = None) -> StrategyRecommendation:
        """Analyze a ticker and return a trading recommendation."""
        pass
    
    @abstractmethod
    def get_params(self) -> dict[str, Any]:
        """Get strategy parameters for display/configuration."""
        pass
    
    def update_config(self, new_config: dict[str, Any]) -> None:
        """Update strategy configuration."""
        self.config.update(new_config)


class MiroFishStrategy(BaseStrategy):
    """Strategy based on MiroFish AI predictions."""
    
    DEFAULT_CONFIG = {
        "confidence_threshold": 0.6,
        "min_confidence_for_trade": 0.55,
        "position_size_multiplier": 1.0,
        "max_position_size_pct": 0.1,  # 10% of portfolio
        "timeframe": "5m",
        "lens": "overall",
        "use_deep_swarm": False,
    }
    
    def __init__(self, config: dict[str, Any] | None = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__("MiroFish AI Strategy", merged_config)
    
    async def analyze(self, ticker: str, context: dict[str, Any] | None = None) -> StrategyRecommendation:
        """Analyze ticker using MiroFish predictions."""
        ctx = context or {}
        portfolio_value = Decimal(str(ctx.get("portfolio_value", 100000)))
        
        try:
            if self.config.get("use_deep_swarm", False):
                result = await mirofish_deep_swarm({
                    "ticker": ticker,
                    "timeframes": ctx.get("timeframes", ["5m", "15m", "1h"]),
                    "lenses": ctx.get("lenses", ["trend", "risk", "catalyst"]),
                })
                
                bias = result.get("overall_bias", "NEUTRAL")
                confidence = result.get("overall_confidence", 0.5)
                alignment = result.get("alignment_score", 0.5)
                
                # Adjust confidence by alignment
                confidence *= (0.5 + alignment * 0.5)
            else:
                result = await mirofish_predict({
                    "ticker": ticker,
                    "timeframe": self.config.get("timeframe", "5m"),
                    "lens": self.config.get("lens", "overall"),
                    "objective": ctx.get("objective", "short-term directional read"),
                })
                
                bias = result.get("directional_bias", "NEUTRAL")
                confidence = result.get("confidence", 0.5)
            
            # Map bias to signal
            signal = self._map_bias_to_signal(bias, confidence)
            
            # Calculate position size
            position_size = self._calculate_position_size(
                confidence, portfolio_value, signal
            )
            
            return StrategyRecommendation(
                ticker=ticker,
                signal=signal,
                confidence=confidence,
                suggested_position_size=position_size,
                rationale={
                    "bias": bias,
                    "mirofish_result": result,
                    "confidence_threshold": self.config["confidence_threshold"],
                },
                strategy_name=self.name,
                metadata={
                    "provider_mode": result.get("provider_mode", "unknown"),
                    "simulation_id": result.get("simulation_id"),
                },
            )
        
        except Exception as e:
            return StrategyRecommendation(
                ticker=ticker,
                signal=StrategySignal.HOLD,
                confidence=0.0,
                suggested_position_size=Decimal("0"),
                rationale={"error": str(e), "strategy": "mirofish"},
                strategy_name=self.name,
            )
    
    def _map_bias_to_signal(self, bias: str, confidence: float) -> StrategySignal:
        """Map MiroFish bias to trading signal."""
        min_conf = self.config.get("min_confidence_for_trade", 0.55)
        
        if confidence < min_conf:
            return StrategySignal.HOLD
        
        bias_upper = bias.upper()
        if bias_upper == "BULLISH":
            return StrategySignal.BUY
        elif bias_upper == "BEARISH":
            return StrategySignal.SELL
        return StrategySignal.HOLD
    
    def _calculate_position_size(
        self,
        confidence: float,
        portfolio_value: Decimal,
        signal: StrategySignal,
    ) -> Decimal:
        """Calculate suggested position size based on confidence."""
        if signal == StrategySignal.HOLD:
            return Decimal("0")
        
        max_pct = Decimal(str(self.config.get("max_position_size_pct", 0.1)))
        multiplier = Decimal(str(self.config.get("position_size_multiplier", 1.0)))
        
        # Scale by confidence
        confidence_factor = Decimal(str(confidence))
        
        base_size = portfolio_value * max_pct * confidence_factor * multiplier
        return base_size.quantize(Decimal("0.01"))
    
    def get_params(self) -> dict[str, Any]:
        """Get strategy parameters."""
        return {
            "name": self.name,
            "type": "mirofish",
            "config": self.config,
            "description": "AI-powered strategy using MiroFish predictions",
            "parameters": [
                {"name": "confidence_threshold", "type": "float", "default": 0.6, "range": [0.0, 1.0]},
                {"name": "min_confidence_for_trade", "type": "float", "default": 0.55, "range": [0.0, 1.0]},
                {"name": "position_size_multiplier", "type": "float", "default": 1.0, "range": [0.1, 3.0]},
                {"name": "max_position_size_pct", "type": "float", "default": 0.1, "range": [0.01, 0.5]},
                {"name": "timeframe", "type": "string", "default": "5m", "options": ["1m", "5m", "15m", "1h", "4h", "1d"]},
                {"name": "use_deep_swarm", "type": "boolean", "default": False},
            ],
        }


class TechnicalIndicatorStrategy(BaseStrategy):
    """Strategy based on technical indicators."""
    
    DEFAULT_CONFIG = {
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "ema_fast": 12,
        "ema_slow": 26,
        "macd_signal": 9,
        "bb_period": 20,
        "bb_std": 2.0,
        "min_confidence": 0.5,
        "max_position_size_pct": 0.1,
    }
    
    def __init__(self, config: dict[str, Any] | None = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__("Technical Indicator Strategy", merged_config)
    
    async def analyze(self, ticker: str, context: dict[str, Any] | None = None) -> StrategyRecommendation:
        """Analyze ticker using technical indicators."""
        ctx = context or {}
        portfolio_value = Decimal(str(ctx.get("portfolio_value", 100000)))
        
        try:
            # Fetch price data
            price_data = await self._fetch_price_data(ticker)
            
            if not price_data or len(price_data) < 30:
                return StrategyRecommendation(
                    ticker=ticker,
                    signal=StrategySignal.HOLD,
                    confidence=0.0,
                    suggested_position_size=Decimal("0"),
                    rationale={"error": "Insufficient price data"},
                    strategy_name=self.name,
                )
            
            # Calculate indicators
            rsi = self._calculate_rsi(price_data)
            ema_signal = self._calculate_ema_signal(price_data)
            macd_signal = self._calculate_macd(price_data)
            bb_signal = self._calculate_bollinger_signal(price_data)
            
            # Combine signals
            signals = [rsi, ema_signal, macd_signal, bb_signal]
            buy_votes = sum(1 for s in signals if s == StrategySignal.BUY)
            sell_votes = sum(1 for s in signals if s == StrategySignal.SELL)
            
            if buy_votes >= 3:
                final_signal = StrategySignal.BUY
                confidence = 0.5 + (buy_votes - sell_votes) * 0.125
            elif sell_votes >= 3:
                final_signal = StrategySignal.SELL
                confidence = 0.5 + (sell_votes - buy_votes) * 0.125
            else:
                final_signal = StrategySignal.HOLD
                confidence = 0.5
            
            confidence = min(confidence, 1.0)
            
            # Calculate position size
            position_size = self._calculate_position_size(confidence, portfolio_value, final_signal)
            
            return StrategyRecommendation(
                ticker=ticker,
                signal=final_signal,
                confidence=confidence,
                suggested_position_size=position_size,
                rationale={
                    "rsi_signal": rsi.value,
                    "ema_signal": ema_signal.value,
                    "macd_signal": macd_signal.value,
                    "bb_signal": bb_signal.value,
                    "buy_votes": buy_votes,
                    "sell_votes": sell_votes,
                    "latest_price": price_data[-1] if price_data else None,
                },
                strategy_name=self.name,
                metadata={
                    "rsi_value": self._calculate_rsi_value(price_data),
                    "ema_fast": self._calculate_ema(price_data, self.config["ema_fast"]),
                    "ema_slow": self._calculate_ema(price_data, self.config["ema_slow"]),
                },
            )
        
        except Exception as e:
            return StrategyRecommendation(
                ticker=ticker,
                signal=StrategySignal.HOLD,
                confidence=0.0,
                suggested_position_size=Decimal("0"),
                rationale={"error": str(e), "strategy": "technical"},
                strategy_name=self.name,
            )
    
    async def _fetch_price_data(self, ticker: str) -> list[float]:
        """Fetch historical price data for calculations."""
        # This would integrate with market data service
        # For now, return mock data structure
        try:
            async with httpx.AsyncClient() as client:
                # Try to fetch from Alpaca or other data source
                url = f"{settings.alpaca_data_base_url}/v2/stocks/{ticker}/bars"
                params = {
                    "timeframe": "1Hour",
                    "limit": 50,
                    "feed": settings.alpaca_data_feed,
                }
                headers = {
                    "APCA-API-KEY-ID": settings.alpaca_api_key,
                    "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
                }
                
                if not settings.alpaca_api_key:
                    # Return mock data for testing
                    return self._generate_mock_price_data()
                
                resp = await client.get(url, params=params, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    bars = data.get("bars", [])
                    return [bar["c"] for bar in bars]
                
                return self._generate_mock_price_data()
        except Exception:
            return self._generate_mock_price_data()
    
    def _generate_mock_price_data(self) -> list[float]:
        """Generate mock price data for testing."""
        import random
        base = 100.0
        prices = [base]
        for _ in range(49):
            change = random.uniform(-0.02, 0.02)
            prices.append(prices[-1] * (1 + change))
        return prices
    
    def _calculate_rsi(self, prices: list[float]) -> StrategySignal:
        """Calculate RSI and return signal."""
        period = self.config["rsi_period"]
        if len(prices) < period + 1:
            return StrategySignal.HOLD
        
        rsi_value = self._calculate_rsi_value(prices)
        
        if rsi_value < self.config["rsi_oversold"]:
            return StrategySignal.BUY
        elif rsi_value > self.config["rsi_overbought"]:
            return StrategySignal.SELL
        return StrategySignal.HOLD
    
    def _calculate_rsi_value(self, prices: list[float]) -> float:
        """Calculate RSI value."""
        period = self.config["rsi_period"]
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            change = prices[-i] - prices[-(i + 1)]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_ema(self, prices: list[float], period: int) -> float:
        """Calculate EMA for given period."""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_ema_signal(self, prices: list[float]) -> StrategySignal:
        """Calculate EMA crossover signal."""
        fast_ema = self._calculate_ema(prices, self.config["ema_fast"])
        slow_ema = self._calculate_ema(prices, self.config["ema_slow"])
        
        # Check previous values for crossover
        if len(prices) >= max(self.config["ema_fast"], self.config["ema_slow"]) + 2:
            prev_fast = self._calculate_ema(prices[:-1], self.config["ema_fast"])
            prev_slow = self._calculate_ema(prices[:-1], self.config["ema_slow"])
            
            if prev_fast <= prev_slow and fast_ema > slow_ema:
                return StrategySignal.BUY
            elif prev_fast >= prev_slow and fast_ema < slow_ema:
                return StrategySignal.SELL
        
        return StrategySignal.HOLD
    
    def _calculate_macd(self, prices: list[float]) -> StrategySignal:
        """Calculate MACD signal."""
        ema12 = self._calculate_ema(prices, 12)
        ema26 = self._calculate_ema(prices, 26)
        macd_line = ema12 - ema26
        
        # Simplified signal line calculation
        signal_line = self._calculate_ema([macd_line] * 9, 9) if macd_line else 0
        
        if macd_line > signal_line:
            return StrategySignal.BUY
        elif macd_line < signal_line:
            return StrategySignal.SELL
        return StrategySignal.HOLD
    
    def _calculate_bollinger_signal(self, prices: list[float]) -> StrategySignal:
        """Calculate Bollinger Bands signal."""
        period = self.config["bb_period"]
        if len(prices) < period:
            return StrategySignal.HOLD
        
        recent = prices[-period:]
        sma = sum(recent) / period
        variance = sum((p - sma) ** 2 for p in recent) / period
        std = variance ** 0.5
        
        upper = sma + self.config["bb_std"] * std
        lower = sma - self.config["bb_std"] * std
        
        current = prices[-1]
        
        if current < lower:
            return StrategySignal.BUY  # Oversold
        elif current > upper:
            return StrategySignal.SELL  # Overbought
        return StrategySignal.HOLD
    
    def _calculate_position_size(
        self,
        confidence: float,
        portfolio_value: Decimal,
        signal: StrategySignal,
    ) -> Decimal:
        """Calculate suggested position size."""
        if signal == StrategySignal.HOLD:
            return Decimal("0")
        
        max_pct = Decimal(str(self.config.get("max_position_size_pct", 0.1)))
        confidence_factor = Decimal(str(confidence))
        
        return (portfolio_value * max_pct * confidence_factor).quantize(Decimal("0.01"))
    
    def get_params(self) -> dict[str, Any]:
        """Get strategy parameters."""
        return {
            "name": self.name,
            "type": "technical",
            "config": self.config,
            "description": "Technical analysis strategy using RSI, EMA, MACD, and Bollinger Bands",
            "parameters": [
                {"name": "rsi_period", "type": "int", "default": 14, "range": [5, 50]},
                {"name": "rsi_overbought", "type": "int", "default": 70, "range": [50, 90]},
                {"name": "rsi_oversold", "type": "int", "default": 30, "range": [10, 50]},
                {"name": "ema_fast", "type": "int", "default": 12, "range": [5, 50]},
                {"name": "ema_slow", "type": "int", "default": 26, "range": [10, 100]},
                {"name": "bb_period", "type": "int", "default": 20, "range": [10, 50]},
                {"name": "bb_std", "type": "float", "default": 2.0, "range": [1.0, 4.0]},
                {"name": "max_position_size_pct", "type": "float", "default": 0.1, "range": [0.01, 0.5]},
            ],
        }


class MultiAgentConsensusStrategy(BaseStrategy):
    """Strategy based on consensus from multiple agents/strategies."""
    
    DEFAULT_CONFIG = {
        "strategies": ["mirofish", "technical"],
        "consensus_threshold": 0.6,
        "min_agreement_count": 2,
        "weight_mirofish": 0.4,
        "weight_technical": 0.3,
        "weight_sentiment": 0.3,
        "max_position_size_pct": 0.15,
    }
    
    def __init__(self, config: dict[str, Any] | None = None):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__("Multi-Agent Consensus Strategy", merged_config)
        
        # Initialize sub-strategies
        self._sub_strategies: dict[str, BaseStrategy] = {}
        if "mirofish" in self.config["strategies"]:
            self._sub_strategies["mirofish"] = MiroFishStrategy()
        if "technical" in self.config["strategies"]:
            self._sub_strategies["technical"] = TechnicalIndicatorStrategy()
    
    async def analyze(self, ticker: str, context: dict[str, Any] | None = None) -> StrategyRecommendation:
        """Analyze ticker using multiple strategies and reach consensus."""
        ctx = context or {}
        portfolio_value = Decimal(str(ctx.get("portfolio_value", 100000)))
        
        # Collect recommendations from all sub-strategies
        recommendations: list[StrategyRecommendation] = []
        
        for name, strategy in self._sub_strategies.items():
            try:
                rec = await strategy.analyze(ticker, ctx)
                recommendations.append(rec)
            except Exception as e:
                recommendations.append(StrategyRecommendation(
                    ticker=ticker,
                    signal=StrategySignal.HOLD,
                    confidence=0.0,
                    suggested_position_size=Decimal("0"),
                    rationale={"error": str(e), "strategy": name},
                    strategy_name=name,
                ))
        
        if not recommendations:
            return StrategyRecommendation(
                ticker=ticker,
                signal=StrategySignal.HOLD,
                confidence=0.0,
                suggested_position_size=Decimal("0"),
                rationale={"error": "No strategies available"},
                strategy_name=self.name,
            )
        
        # Calculate weighted consensus
        buy_weight = 0.0
        sell_weight = 0.0
        hold_weight = 0.0
        total_confidence = 0.0
        
        for rec in recommendations:
            weight = self.config.get(f"weight_{rec.strategy_name}", 1.0 / len(recommendations))
            
            if rec.signal == StrategySignal.BUY:
                buy_weight += weight * rec.confidence
            elif rec.signal == StrategySignal.SELL:
                sell_weight += weight * rec.confidence
            else:
                hold_weight += weight * rec.confidence
            
            total_confidence += rec.confidence * weight
        
        # Determine final signal
        max_weight = max(buy_weight, sell_weight, hold_weight)
        
        if max_weight == buy_weight and buy_weight >= self.config["consensus_threshold"]:
            final_signal = StrategySignal.BUY
            confidence = buy_weight
        elif max_weight == sell_weight and sell_weight >= self.config["consensus_threshold"]:
            final_signal = StrategySignal.SELL
            confidence = sell_weight
        else:
            final_signal = StrategySignal.HOLD
            confidence = hold_weight
        
        # Count agreements
        agreements = sum(
            1 for rec in recommendations
            if rec.signal == final_signal and rec.confidence >= 0.5
        )
        
        if agreements < self.config["min_agreement_count"]:
            final_signal = StrategySignal.HOLD
            confidence *= 0.5
        
        # Calculate position size
        position_size = self._calculate_position_size(confidence, portfolio_value, final_signal)
        
        return StrategyRecommendation(
            ticker=ticker,
            signal=final_signal,
            confidence=confidence,
            suggested_position_size=position_size,
            rationale={
                "individual_recommendations": [
                    {
                        "strategy": rec.strategy_name,
                        "signal": rec.signal.value,
                        "confidence": rec.confidence,
                    }
                    for rec in recommendations
                ],
                "buy_weight": buy_weight,
                "sell_weight": sell_weight,
                "hold_weight": hold_weight,
                "agreements": agreements,
                "consensus_threshold": self.config["consensus_threshold"],
            },
            strategy_name=self.name,
            metadata={
                "sub_strategies_used": list(self._sub_strategies.keys()),
                "weighted_average_confidence": total_confidence,
            },
        )
    
    def _calculate_position_size(
        self,
        confidence: float,
        portfolio_value: Decimal,
        signal: StrategySignal,
    ) -> Decimal:
        """Calculate suggested position size."""
        if signal == StrategySignal.HOLD:
            return Decimal("0")
        
        max_pct = Decimal(str(self.config.get("max_position_size_pct", 0.15)))
        confidence_factor = Decimal(str(confidence))
        
        return (portfolio_value * max_pct * confidence_factor).quantize(Decimal("0.01"))
    
    def get_params(self) -> dict[str, Any]:
        """Get strategy parameters."""
        return {
            "name": self.name,
            "type": "consensus",
            "config": self.config,
            "description": "Multi-agent consensus strategy combining multiple analysis methods",
            "parameters": [
                {"name": "strategies", "type": "list", "default": ["mirofish", "technical"], "options": ["mirofish", "technical", "sentiment"]},
                {"name": "consensus_threshold", "type": "float", "default": 0.6, "range": [0.5, 0.9]},
                {"name": "min_agreement_count", "type": "int", "default": 2, "range": [1, 5]},
                {"name": "weight_mirofish", "type": "float", "default": 0.4, "range": [0.0, 1.0]},
                {"name": "weight_technical", "type": "float", "default": 0.3, "range": [0.0, 1.0]},
                {"name": "weight_sentiment", "type": "float", "default": 0.3, "range": [0.0, 1.0]},
                {"name": "max_position_size_pct", "type": "float", "default": 0.15, "range": [0.01, 0.5]},
            ],
        }


class CustomStrategyBuilder:
    """Builder for creating custom trading strategies."""
    
    def __init__(self):
        self._conditions: list[Callable[[dict[str, Any]], tuple[bool, float]]] = []
        self._config: dict[str, Any] = {}
        self._name: str = "Custom Strategy"
    
    def set_name(self, name: str) -> CustomStrategyBuilder:
        """Set the strategy name."""
        self._name = name
        return self
    
    def add_condition(
        self,
        condition: Callable[[dict[str, Any]], tuple[bool, float]],
    ) -> CustomStrategyBuilder:
        """Add a condition function that returns (should_trigger, confidence)."""
        self._conditions.append(condition)
        return self
    
    def set_config(self, config: dict[str, Any]) -> CustomStrategyBuilder:
        """Set strategy configuration."""
        self._config = config
        return self
    
    def build(self) -> BaseStrategy:
        """Build and return the custom strategy."""
        
        class CustomStrategy(BaseStrategy):
            def __init__(inner_self, name: str, config: dict[str, Any], conditions: list):
                super().__init__(name, config)
                inner_self._conditions = conditions
            
            async def analyze(inner_self, ticker: str, context: dict[str, Any] | None = None) -> StrategyRecommendation:
                ctx = context or {}
                portfolio_value = Decimal(str(ctx.get("portfolio_value", 100000)))
                
                # Evaluate all conditions
                buy_score = 0.0
                sell_score = 0.0
                triggered_conditions = []
                
                for i, condition in enumerate(inner_self._conditions):
                    try:
                        should_trigger, confidence = condition(ctx)
                        if should_trigger:
                            if confidence > 0:
                                buy_score += confidence
                            else:
                                sell_score += abs(confidence)
                            triggered_conditions.append(i)
                    except Exception as e:
                        triggered_conditions.append(f"error_{i}: {e}")
                
                # Determine signal
                if buy_score > sell_score and buy_score >= inner_self.config.get("min_score", 0.5):
                    signal = StrategySignal.BUY
                    confidence = min(buy_score, 1.0)
                elif sell_score > buy_score and sell_score >= inner_self.config.get("min_score", 0.5):
                    signal = StrategySignal.SELL
                    confidence = min(sell_score, 1.0)
                else:
                    signal = StrategySignal.HOLD
                    confidence = 0.5
                
                # Calculate position size
                max_pct = Decimal(str(inner_self.config.get("max_position_size_pct", 0.1)))
                position_size = portfolio_value * max_pct * Decimal(str(confidence)) if signal != StrategySignal.HOLD else Decimal("0")
                
                return StrategyRecommendation(
                    ticker=ticker,
                    signal=signal,
                    confidence=confidence,
                    suggested_position_size=position_size.quantize(Decimal("0.01")),
                    rationale={
                        "triggered_conditions": triggered_conditions,
                        "buy_score": buy_score,
                        "sell_score": sell_score,
                    },
                    strategy_name=inner_self.name,
                )
            
            def get_params(inner_self) -> dict[str, Any]:
                return {
                    "name": inner_self.name,
                    "type": "custom",
                    "config": inner_self.config,
                    "description": "User-defined custom strategy",
                    "parameters": [
                        {"name": "min_score", "type": "float", "default": 0.5, "range": [0.0, 1.0]},
                        {"name": "max_position_size_pct", "type": "float", "default": 0.1, "range": [0.01, 0.5]},
                    ],
                }
        
        return CustomStrategy(self._name, self._config, self._conditions)


# Strategy registry
STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "mirofish": MiroFishStrategy,
    "technical": TechnicalIndicatorStrategy,
    "consensus": MultiAgentConsensusStrategy,
}


def get_strategy(strategy_type: str, config: dict[str, Any] | None = None) -> BaseStrategy:
    """Factory function to get a strategy by type."""
    strategy_class = STRATEGY_REGISTRY.get(strategy_type)
    if not strategy_class:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    return strategy_class(config)


def list_available_strategies() -> list[dict[str, Any]]:
    """List all available strategies with their parameters."""
    strategies = []
    for name, strategy_class in STRATEGY_REGISTRY.items():
        try:
            instance = strategy_class()
            strategies.append(instance.get_params())
        except Exception as e:
            strategies.append({
                "name": name,
                "type": name,
                "error": str(e),
            })
    return strategies
