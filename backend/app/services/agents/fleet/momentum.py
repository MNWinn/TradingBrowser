"""
Momentum Agent - Tracks momentum indicators and divergences.

This agent analyzes momentum indicators including RSI, MACD, Stochastic,
and identifies divergences between price and momentum for early signals.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class DivergenceType(Enum):
    """Types of price-momentum divergences."""
    BULLISH = "bullish"  # Price lower low, momentum higher low
    BEARISH = "bearish"  # Price higher high, momentum lower high
    HIDDEN_BULLISH = "hidden_bullish"  # Price higher low, momentum lower low
    HIDDEN_BEARISH = "hidden_bearish"  # Price lower high, momentum higher high


@dataclass
class Divergence:
    """Represents a detected divergence."""
    type: DivergenceType
    indicator: str
    confidence: float
    price_pivot_1: float
    price_pivot_2: float
    mom_pivot_1: float
    mom_pivot_2: float
    description: str


class MomentumAgent(BaseAgent):
    """
    Momentum analysis specialist with divergence detection.
    
    Specialization:
    - RSI momentum tracking
    - MACD momentum and signal analysis
    - Stochastic oscillator analysis
    - Price-momentum divergence detection
    - Rate of change (ROC) analysis
    - Momentum crossovers and threshold breaks
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "momentum",
            agent_type="momentum",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "momentum_analysis"
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.stoch_k = 14
        self.stoch_d = 3

    async def _run(self, payload: dict) -> dict:
        """
        Execute momentum analysis.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with momentum indicators and divergence signals
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        
        self.log(f"Starting momentum analysis for {ticker} on {timeframe}", "info")
        
        # Fetch data
        bars_data = get_bars_snapshot(ticker, timeframe=timeframe, limit=lookback)
        bars = bars_data.get("bars", [])
        
        if len(bars) < 30:
            return {
                "agent": self.agent_type,
                "agent_id": self.agent_id,
                "ticker": ticker,
                "timeframe": timeframe,
                "error": f"Insufficient data: {len(bars)} bars (minimum 30 required)",
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Calculate momentum indicators
        indicators = self._calculate_indicators(df)
        
        # Detect divergences
        divergences = self._detect_divergences(df, indicators)
        
        # Analyze momentum state
        momentum_state = self._analyze_momentum_state(indicators)
        
        # Calculate confidence
        confidence_data = self._calculate_confidence(indicators, divergences, df)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(momentum_state, divergences, indicators)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "indicators": indicators,
            "momentum_state": momentum_state,
            "divergences": [
                {
                    "type": d.type.value,
                    "indicator": d.indicator,
                    "confidence": round(d.confidence, 3),
                    "description": d.description,
                }
                for d in divergences[:5]
            ],
            "divergence_count": len(divergences),
            "recommendation": recommendation,
            "confidence": confidence_data["overall_confidence"],
            "confidence_breakdown": confidence_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Momentum analysis complete for {ticker}: {recommendation}", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _prepare_data(self, bars: list) -> pd.DataFrame:
        """Prepare price data."""
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate all momentum indicators."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        # RSI
        rsi = self._calculate_rsi(close, self.rsi_period)
        
        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(close)
        
        # Stochastic
        stoch_k, stoch_d = self._calculate_stochastic(high, low, close)
        
        # Rate of Change (ROC)
        roc_10 = ((close - close.shift(10)) / close.shift(10)) * 100
        roc_20 = ((close - close.shift(20)) / close.shift(20)) * 100
        
        # Momentum (price difference)
        momentum = close - close.shift(10)
        
        # Williams %R
        williams_r = self._calculate_williams_r(high, low, close)
        
        # CCI (Commodity Channel Index)
        cci = self._calculate_cci(high, low, close)
        
        # Get latest values
        latest = {
            "rsi": round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None,
            "rsi_prev": round(rsi.iloc[-2], 2) if len(rsi) > 1 and not pd.isna(rsi.iloc[-2]) else None,
            "macd": {
                "line": round(macd_line.iloc[-1], 4) if not pd.isna(macd_line.iloc[-1]) else None,
                "signal": round(signal_line.iloc[-1], 4) if not pd.isna(signal_line.iloc[-1]) else None,
                "histogram": round(histogram.iloc[-1], 4) if not pd.isna(histogram.iloc[-1]) else None,
                "line_prev": round(macd_line.iloc[-2], 4) if len(macd_line) > 1 else None,
                "signal_prev": round(signal_line.iloc[-2], 4) if len(signal_line) > 1 else None,
            },
            "stochastic": {
                "k": round(stoch_k.iloc[-1], 2) if not pd.isna(stoch_k.iloc[-1]) else None,
                "d": round(stoch_d.iloc[-1], 2) if not pd.isna(stoch_d.iloc[-1]) else None,
                "k_prev": round(stoch_k.iloc[-2], 2) if len(stoch_k) > 1 else None,
            },
            "roc_10": round(roc_10.iloc[-1], 2) if not pd.isna(roc_10.iloc[-1]) else None,
            "roc_20": round(roc_20.iloc[-1], 2) if not pd.isna(roc_20.iloc[-1]) else None,
            "momentum": round(momentum.iloc[-1], 2) if not pd.isna(momentum.iloc[-1]) else None,
            "williams_r": round(williams_r.iloc[-1], 2) if not pd.isna(williams_r.iloc[-1]) else None,
            "cci": round(cci.iloc[-1], 2) if not pd.isna(cci.iloc[-1]) else None,
        }
        
        # Add historical data for divergence detection (last 50 periods)
        historical = {
            "close": close.tail(50).tolist(),
            "rsi": rsi.tail(50).tolist(),
            "macd_line": macd_line.tail(50).tolist(),
            "high": high.tail(50).tolist(),
            "low": low.tail(50).tolist(),
        }
        
        return {
            "latest": latest,
            "historical": historical,
        }

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD."""
        ema_fast = prices.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = prices.ewm(span=self.macd_slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram

    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic Oscillator."""
        lowest_low = low.rolling(window=self.stoch_k).min()
        highest_high = high.rolling(window=self.stoch_k).max()
        
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=self.stoch_d).mean()
        
        return k, d

    def _calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Williams %R."""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
        return williams_r

    def _calculate_cci(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index."""
        typical_price = (high + low + close) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mean_deviation = typical_price.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (typical_price - sma_tp) / (0.015 * mean_deviation)
        return cci

    def _detect_divergences(self, df: pd.DataFrame, indicators: dict) -> List[Divergence]:
        """Detect price-momentum divergences."""
        divergences = []
        
        hist = indicators["historical"]
        close = np.array(hist["close"])
        rsi = np.array(hist["rsi"])
        macd = np.array(hist["macd_line"])
        
        # Find local extrema in price and indicators
        price_highs = self._find_pivots(close, high=True)
        price_lows = self._find_pivots(close, high=False)
        
        rsi_highs = self._find_pivots(rsi, high=True)
        rsi_lows = self._find_pivots(rsi, high=False)
        
        macd_highs = self._find_pivots(macd, high=True)
        macd_lows = self._find_pivots(macd, high=False)
        
        # Regular bullish divergence: price lower low, RSI higher low
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            for i in range(1, min(len(price_lows), len(rsi_lows))):
                p1, p2 = price_lows[-(i+1)], price_lows[-i]
                r1, r2 = rsi_lows[-(i+1)], rsi_lows[-i]
                
                if close[p1] > close[p2] and rsi[r1] < rsi[r2]:  # Price lower, RSI higher
                    confidence = self._divergence_confidence(
                        close[p1], close[p2], rsi[r1], rsi[r2], "bullish"
                    )
                    divergences.append(Divergence(
                        type=DivergenceType.BULLISH,
                        indicator="RSI",
                        confidence=confidence,
                        price_pivot_1=round(close[p1], 2),
                        price_pivot_2=round(close[p2], 2),
                        mom_pivot_1=round(rsi[r1], 2),
                        mom_pivot_2=round(rsi[r2], 2),
                        description=f"RSI Bullish Divergence: Price {close[p1]:.2f}->{close[p2]:.2f}, RSI {rsi[r1]:.2f}->{rsi[r2]:.2f}"
                    ))
        
        # Regular bearish divergence: price higher high, RSI lower high
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            for i in range(1, min(len(price_highs), len(rsi_highs))):
                p1, p2 = price_highs[-(i+1)], price_highs[-i]
                r1, r2 = rsi_highs[-(i+1)], rsi_highs[-i]
                
                if close[p1] < close[p2] and rsi[r1] > rsi[r2]:  # Price higher, RSI lower
                    confidence = self._divergence_confidence(
                        close[p1], close[p2], rsi[r1], rsi[r2], "bearish"
                    )
                    divergences.append(Divergence(
                        type=DivergenceType.BEARISH,
                        indicator="RSI",
                        confidence=confidence,
                        price_pivot_1=round(close[p1], 2),
                        price_pivot_2=round(close[p2], 2),
                        mom_pivot_1=round(rsi[r1], 2),
                        mom_pivot_2=round(rsi[r2], 2),
                        description=f"RSI Bearish Divergence: Price {close[p1]:.2f}->{close[p2]:.2f}, RSI {rsi[r1]:.2f}->{rsi[r2]:.2f}"
                    ))
        
        # MACD divergences
        if len(price_lows) >= 2 and len(macd_lows) >= 2:
            for i in range(1, min(len(price_lows), len(macd_lows))):
                p1, p2 = price_lows[-(i+1)], price_lows[-i]
                m1, m2 = macd_lows[-(i+1)], macd_lows[-i]
                
                if close[p1] > close[p2] and macd[m1] < macd[m2]:
                    confidence = self._divergence_confidence(
                        close[p1], close[p2], macd[m1], macd[m2], "bullish"
                    )
                    divergences.append(Divergence(
                        type=DivergenceType.BULLISH,
                        indicator="MACD",
                        confidence=confidence,
                        price_pivot_1=round(close[p1], 2),
                        price_pivot_2=round(close[p2], 2),
                        mom_pivot_1=round(macd[m1], 4),
                        mom_pivot_2=round(macd[m2], 4),
                        description=f"MACD Bullish Divergence"
                    ))
        
        if len(price_highs) >= 2 and len(macd_highs) >= 2:
            for i in range(1, min(len(price_highs), len(macd_highs))):
                p1, p2 = price_highs[-(i+1)], price_highs[-i]
                m1, m2 = macd_highs[-(i+1)], macd_highs[-i]
                
                if close[p1] < close[p2] and macd[m1] > macd[m2]:
                    confidence = self._divergence_confidence(
                        close[p1], close[p2], macd[m1], macd[m2], "bearish"
                    )
                    divergences.append(Divergence(
                        type=DivergenceType.BEARISH,
                        indicator="MACD",
                        confidence=confidence,
                        price_pivot_1=round(close[p1], 2),
                        price_pivot_2=round(close[p2], 2),
                        mom_pivot_1=round(macd[m1], 4),
                        mom_pivot_2=round(macd[m2], 4),
                        description=f"MACD Bearish Divergence"
                    ))
        
        # Sort by confidence
        divergences.sort(key=lambda d: d.confidence, reverse=True)
        return divergences

    def _find_pivots(self, data: np.ndarray, high: bool = True, window: int = 3) -> List[int]:
        """Find pivot points in data."""
        pivots = []
        for i in range(window, len(data) - window):
            if high:
                if data[i] == max(data[i-window:i+window+1]):
                    pivots.append(i)
            else:
                if data[i] == min(data[i-window:i+window+1]):
                    pivots.append(i)
        return pivots

    def _divergence_confidence(
        self,
        price_1: float, price_2: float,
        mom_1: float, mom_2: float,
        div_type: str
    ) -> float:
        """Calculate confidence score for a divergence."""
        # Price move magnitude
        price_change = abs(price_2 - price_1) / price_1
        
        # Momentum move magnitude (normalized)
        if div_type == "bullish":
            mom_change = abs(mom_2 - mom_1) / max(abs(mom_1), 1)
        else:
            mom_change = abs(mom_1 - mom_2) / max(abs(mom_2), 1)
        
        # Base confidence on magnitude of divergence
        confidence = 0.5 + (price_change * 2) + (mom_change * 0.5)
        return min(confidence, 0.95)

    def _analyze_momentum_state(self, indicators: dict) -> dict:
        """Analyze overall momentum state."""
        latest = indicators["latest"]
        
        state = {
            "rsi_state": "neutral",
            "macd_state": "neutral",
            "stoch_state": "neutral",
            "overall": "neutral",
        }
        
        # RSI state
        rsi = latest.get("rsi")
        if rsi is not None:
            if rsi > 70:
                state["rsi_state"] = "overbought"
            elif rsi < 30:
                state["rsi_state"] = "oversold"
            elif rsi > 50:
                state["rsi_state"] = "bullish"
            else:
                state["rsi_state"] = "bearish"
        
        # MACD state
        macd = latest.get("macd", {})
        macd_line = macd.get("line")
        signal_line = macd.get("signal")
        histogram = macd.get("histogram")
        macd_line_prev = macd.get("line_prev")
        signal_prev = macd.get("signal_prev")
        
        if macd_line is not None and signal_line is not None:
            if macd_line > signal_line:
                state["macd_state"] = "bullish"
            else:
                state["macd_state"] = "bearish"
            
            # Check for crossover
            if macd_line_prev is not None and signal_prev is not None:
                if macd_line > signal_line and macd_line_prev <= signal_prev:
                    state["macd_state"] = "bullish_crossover"
                elif macd_line < signal_line and macd_line_prev >= signal_prev:
                    state["macd_state"] = "bearish_crossover"
        
        # Stochastic state
        stoch = latest.get("stochastic", {})
        k = stoch.get("k")
        d = stoch.get("d")
        k_prev = stoch.get("k_prev")
        
        if k is not None and d is not None:
            if k > 80:
                state["stoch_state"] = "overbought"
            elif k < 20:
                state["stoch_state"] = "oversold"
            elif k > d:
                state["stoch_state"] = "bullish"
            else:
                state["stoch_state"] = "bearish"
        
        # Overall momentum
        bullish_signals = sum([
            state["rsi_state"] in ["bullish", "oversold"],
            state["macd_state"] in ["bullish", "bullish_crossover"],
            state["stoch_state"] in ["bullish", "oversold"],
        ])
        
        bearish_signals = sum([
            state["rsi_state"] in ["bearish", "overbought"],
            state["macd_state"] in ["bearish", "bearish_crossover"],
            state["stoch_state"] in ["bearish", "overbought"],
        ])
        
        if bullish_signals >= 2:
            state["overall"] = "bullish"
        elif bearish_signals >= 2:
            state["overall"] = "bearish"
        elif bullish_signals > bearish_signals:
            state["overall"] = "weak_bullish"
        elif bearish_signals > bullish_signals:
            state["overall"] = "weak_bearish"
        
        return state

    def _calculate_confidence(
        self,
        indicators: dict,
        divergences: List[Divergence],
        df: pd.DataFrame
    ) -> dict:
        """Calculate overall confidence."""
        # Data quality
        data_quality = min(len(df) / 100, 1.0)
        
        # Divergence quality
        div_confidence = max([d.confidence for d in divergences]) if divergences else 0.5
        
        # Indicator alignment
        momentum_state = self._analyze_momentum_state(indicators)
        state_confidence = 0.7 if momentum_state["overall"] in ["bullish", "bearish"] else 0.5
        
        overall = (data_quality * 0.2 + div_confidence * 0.4 + state_confidence * 0.4)
        
        return {
            "overall_confidence": round(min(overall, 0.95), 3),
            "data_quality": round(data_quality, 3),
            "divergence_confidence": round(div_confidence, 3),
            "state_confidence": round(state_confidence, 3),
        }

    def _determine_recommendation(
        self,
        momentum_state: dict,
        divergences: List[Divergence],
        indicators: dict
    ) -> str:
        """Determine trading recommendation."""
        overall = momentum_state.get("overall", "neutral")
        
        # Check for strong divergences first (high confidence signals)
        strong_div = [d for d in divergences if d.confidence > 0.7]
        
        if strong_div:
            div = strong_div[0]
            if div.type in [DivergenceType.BULLISH, DivergenceType.HIDDEN_BULLISH]:
                return "LONG"
            elif div.type in [DivergenceType.BEARISH, DivergenceType.HIDDEN_BEARISH]:
                return "SHORT"
        
        # Use momentum state
        if overall == "bullish":
            return "LONG"
        elif overall == "bearish":
            return "SHORT"
        elif overall in ["weak_bullish"]:
            return "WATCHLIST_LONG"
        elif overall in ["weak_bearish"]:
            return "WATCHLIST_SHORT"
        
        return "WATCHLIST"

    async def _store_results(self, output: dict) -> None:
        """Store agent results in database."""
        try:
            db = SessionLocal()
            try:
                run = SwarmAgentRun(
                    task_id=f"{self.agent_id}-{datetime.now(timezone.utc).timestamp()}",
                    agent_name=self.agent_type,
                    recommendation=output.get("recommendation"),
                    confidence=output.get("confidence"),
                    output=output,
                )
                db.add(run)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.log(f"Failed to store results: {e}", "error")


# Convenience function
async def run_momentum_analysis(
    ticker: str,
    timeframe: str = "5m",
    lookback: int = 100,
) -> dict:
    """Run momentum analysis directly."""
    agent = MomentumAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"momentum-direct-{ticker}-{datetime.now(timezone.utc).timestamp()}",
        agent_type="momentum",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "lookback": lookback,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
