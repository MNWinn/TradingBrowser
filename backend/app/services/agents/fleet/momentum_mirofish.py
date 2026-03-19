"""
Momentum Agent with MiroFish Confirmation

This agent analyzes momentum indicators and uses MiroFish
predictions for signal confirmation.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
from enum import Enum

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot
from app.services.agents.fleet.mirofish_assessment import run_mirofish_assessment
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class DivergenceType(Enum):
    """Types of price-momentum divergences."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    HIDDEN_BULLISH = "hidden_bullish"
    HIDDEN_BEARISH = "hidden_bearish"


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
    Momentum analysis with MiroFish confirmation.
    
    Specialization:
    - RSI, MACD, Stochastic analysis
    - Divergence detection with MiroFish validation
    - Momentum crossovers with AI confirmation
    - Multi-timeframe momentum alignment
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
        self.specialization = "momentum_analysis_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute momentum analysis with MiroFish confirmation.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with momentum indicators and MiroFish-enhanced signals
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
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
        
        # Get MiroFish confirmation
        mirofish_data = None
        if include_mirofish:
            try:
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
            except Exception as e:
                self.log(f"MiroFish confirmation failed: {e}", "warning")
        
        # Generate recommendation with MiroFish
        recommendation, confidence = self._generate_recommendation(indicators, divergences, mirofish_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "indicators": indicators,
            "divergences": [self._divergence_to_dict(d) for d in divergences],
            "divergence_count": len(divergences),
            "recommendation": recommendation,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Momentum analysis complete for {ticker}: {recommendation} (confidence: {confidence:.2f})", "info")
        
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

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate momentum indicators."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = close.ewm(span=12).mean()
        ema_26 = close.ewm(span=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9).mean()
        macd_hist = macd - macd_signal
        
        # Stochastic
        lowest_low = low.rolling(window=14).min()
        highest_high = high.rolling(window=14).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=3).mean()
        
        # Rate of Change
        roc = ((close - close.shift(10)) / close.shift(10)) * 100
        
        return {
            "rsi": round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None,
            "rsi_prev": round(rsi.iloc[-5], 2) if len(rsi) >= 5 and not pd.isna(rsi.iloc[-5]) else None,
            "macd": round(macd.iloc[-1], 4) if not pd.isna(macd.iloc[-1]) else None,
            "macd_signal": round(macd_signal.iloc[-1], 4) if not pd.isna(macd_signal.iloc[-1]) else None,
            "macd_hist": round(macd_hist.iloc[-1], 4) if not pd.isna(macd_hist.iloc[-1]) else None,
            "stoch_k": round(k.iloc[-1], 2) if not pd.isna(k.iloc[-1]) else None,
            "stoch_d": round(d.iloc[-1], 2) if not pd.isna(d.iloc[-1]) else None,
            "roc": round(roc.iloc[-1], 2) if not pd.isna(roc.iloc[-1]) else None,
            "price": round(close.iloc[-1], 2),
        }

    def _detect_divergences(self, df: pd.DataFrame, indicators: Dict) -> List[Divergence]:
        """Detect price-momentum divergences."""
        divergences = []
        close = df["close"].values
        
        # Calculate RSI for divergence detection
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).values
        
        # Find pivot points (simplified)
        window = 5
        for i in range(window, len(close) - window - 5):
            # Price lower low, RSI higher low (bullish divergence)
            if close[i] < close[i-5] and close[i] < close[i+5]:
                if rsi[i] > rsi[i-5] and not np.isnan(rsi[i]):
                    divergences.append(Divergence(
                        type=DivergenceType.BULLISH,
                        indicator="RSI",
                        confidence=0.65,
                        price_pivot_1=round(close[i-5], 2),
                        price_pivot_2=round(close[i], 2),
                        mom_pivot_1=round(rsi[i-5], 2),
                        mom_pivot_2=round(rsi[i], 2),
                        description="Bullish divergence: Price lower low, RSI higher low"
                    ))
            
            # Price higher high, RSI lower high (bearish divergence)
            if close[i] > close[i-5] and close[i] > close[i+5]:
                if rsi[i] < rsi[i-5] and not np.isnan(rsi[i]):
                    divergences.append(Divergence(
                        type=DivergenceType.BEARISH,
                        indicator="RSI",
                        confidence=0.65,
                        price_pivot_1=round(close[i-5], 2),
                        price_pivot_2=round(close[i], 2),
                        mom_pivot_1=round(rsi[i-5], 2),
                        mom_pivot_2=round(rsi[i], 2),
                        description="Bearish divergence: Price higher high, RSI lower high"
                    ))
        
        return divergences[-3:]  # Return last 3 divergences

    def _generate_recommendation(self, indicators: Dict, divergences: List[Divergence], mirofish_data: Optional[dict]) -> tuple:
        """Generate trading recommendation with MiroFish confirmation."""
        signals = []
        
        # RSI signals
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi < 30:
                signals.append(("LONG", 0.7))
            elif rsi > 70:
                signals.append(("SHORT", 0.7))
        
        # MACD signals
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None:
            if macd_hist > 0:
                signals.append(("LONG", 0.6))
            else:
                signals.append(("SHORT", 0.6))
        
        # Divergence signals
        for div in divergences:
            if div.type == DivergenceType.BULLISH:
                signals.append(("LONG", div.confidence))
            elif div.type == DivergenceType.BEARISH:
                signals.append(("SHORT", div.confidence))
        
        # Calculate base recommendation
        long_score = sum(conf for sig, conf in signals if sig == "LONG")
        short_score = sum(conf for sig, conf in signals if sig == "SHORT")
        
        if long_score > short_score:
            base_rec = "LONG"
            base_conf = min(0.9, long_score / max(len(signals), 1))
        elif short_score > long_score:
            base_rec = "SHORT"
            base_conf = min(0.9, short_score / max(len(signals), 1))
        else:
            base_rec = "NEUTRAL"
            base_conf = 0.5
        
        # Incorporate MiroFish
        if mirofish_data:
            bias = mirofish_data.get("directional_bias", "NEUTRAL")
            miro_conf = mirofish_data.get("confidence", 0.5)
            
            if base_rec == "LONG" and bias == "BULLISH":
                return "LONG", min(0.95, base_conf * 0.6 + miro_conf * 0.4)
            elif base_rec == "SHORT" and bias == "BEARISH":
                return "SHORT", min(0.95, base_conf * 0.6 + miro_conf * 0.4)
            elif base_rec == "NEUTRAL" and bias != "NEUTRAL":
                return "LONG" if bias == "BULLISH" else "SHORT", miro_conf * 0.8
            elif (base_rec == "LONG" and bias == "BEARISH") or (base_rec == "SHORT" and bias == "BULLISH"):
                return "NO_TRADE", 0.4
        
        return base_rec, base_conf

    def _divergence_to_dict(self, div: Divergence) -> dict:
        """Convert divergence to dictionary."""
        return {
            "type": div.type.value,
            "indicator": div.indicator,
            "confidence": div.confidence,
            "price_pivot_1": div.price_pivot_1,
            "price_pivot_2": div.price_pivot_2,
            "mom_pivot_1": div.mom_pivot_1,
            "mom_pivot_2": div.mom_pivot_2,
            "description": div.description,
        }

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
    include_mirofish: bool = True,
) -> dict:
    """Run momentum analysis directly."""
    agent = MomentumAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"momentum-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="momentum",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
