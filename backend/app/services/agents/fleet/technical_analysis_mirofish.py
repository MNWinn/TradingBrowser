"""
Technical Analysis Agent with MiroFish Integration

This agent performs technical analysis and incorporates MiroFish predictions
for enhanced signal confirmation.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot, get_quote_snapshot
from app.services.agents.fleet.mirofish_assessment import run_mirofish_assessment
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class TechnicalAnalysisAgent(BaseAgent):
    """
    Technical analysis specialist with MiroFish integration.
    
    Specialization:
    - Multi-timeframe technical indicator analysis
    - Price action pattern recognition
    - Trend analysis with MiroFish confirmation
    - Signal generation with confidence scoring
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "technical_analysis",
            agent_type="technical_analysis",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "technical_analysis_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute technical analysis with MiroFish integration.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'limit'
            
        Returns:
            Dict with technical analysis and MiroFish-enhanced signals
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        limit = payload.get("limit", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
        self.log(f"Starting technical analysis for {ticker} on {timeframe}", "info")
        
        # Get market data
        bars_data = get_bars_snapshot(ticker, timeframe=timeframe, limit=limit)
        bars = bars_data.get("bars", [])
        quote = get_quote_snapshot(ticker)
        
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
        
        # Prepare DataFrame
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        
        # Calculate technical indicators
        indicators = self._calculate_indicators(df)
        
        # Generate technical signals
        signals = self._generate_signals(df, indicators)
        
        # Get MiroFish prediction if enabled
        mirofish_data = None
        if include_mirofish:
            try:
                self.log(f"Fetching MiroFish prediction for {ticker}", "info")
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
            except Exception as e:
                self.log(f"MiroFish prediction failed: {e}", "warning")
        
        # Combine technical and MiroFish signals
        recommendation, confidence = self._combine_signals(signals, mirofish_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "indicators": indicators,
            "signals": signals,
            "recommendation": recommendation,
            "confidence": confidence,
            "current_price": quote.get("price"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Technical analysis complete for {ticker}: {recommendation} (confidence: {confidence:.2f})", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _calculate_indicators(self, df: pd.DataFrame) -> dict:
        """Calculate technical indicators."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        
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
        
        # Bollinger Bands
        sma_20 = close.rolling(window=20).mean()
        std_20 = close.rolling(window=20).std()
        bb_upper = sma_20 + (std_20 * 2)
        bb_lower = sma_20 - (std_20 * 2)
        
        # VWAP
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        
        # Moving Averages
        sma_50 = close.rolling(window=50).mean() if len(close) >= 50 else None
        sma_200 = close.rolling(window=200).mean() if len(close) >= 200 else None
        
        return {
            "rsi": round(rsi.iloc[-1], 2) if not pd.isna(rsi.iloc[-1]) else None,
            "macd": round(macd.iloc[-1], 4) if not pd.isna(macd.iloc[-1]) else None,
            "macd_signal": round(macd_signal.iloc[-1], 4) if not pd.isna(macd_signal.iloc[-1]) else None,
            "macd_hist": round(macd_hist.iloc[-1], 4) if not pd.isna(macd_hist.iloc[-1]) else None,
            "bb_upper": round(bb_upper.iloc[-1], 2) if not pd.isna(bb_upper.iloc[-1]) else None,
            "bb_lower": round(bb_lower.iloc[-1], 2) if not pd.isna(bb_lower.iloc[-1]) else None,
            "bb_middle": round(sma_20.iloc[-1], 2) if not pd.isna(sma_20.iloc[-1]) else None,
            "vwap": round(vwap.iloc[-1], 2) if not pd.isna(vwap.iloc[-1]) else None,
            "sma_20": round(sma_20.iloc[-1], 2) if not pd.isna(sma_20.iloc[-1]) else None,
            "sma_50": round(sma_50.iloc[-1], 2) if sma_50 is not None and not pd.isna(sma_50.iloc[-1]) else None,
            "sma_200": round(sma_200.iloc[-1], 2) if sma_200 is not None and not pd.isna(sma_200.iloc[-1]) else None,
            "price": round(close.iloc[-1], 2),
        }

    def _generate_signals(self, df: pd.DataFrame, indicators: dict) -> list:
        """Generate technical signals."""
        signals = []
        close = df["close"].iloc[-1]
        
        # RSI signals
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi < 30:
                signals.append({"indicator": "RSI", "signal": "OVERSOLD", "strength": 0.7})
            elif rsi > 70:
                signals.append({"indicator": "RSI", "signal": "OVERBOUGHT", "strength": 0.7})
        
        # MACD signals
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None:
            if macd_hist > 0:
                signals.append({"indicator": "MACD", "signal": "BULLISH", "strength": 0.6})
            else:
                signals.append({"indicator": "MACD", "signal": "BEARISH", "strength": 0.6})
        
        # Price vs VWAP
        vwap = indicators.get("vwap")
        if vwap is not None:
            if close > vwap * 1.01:
                signals.append({"indicator": "VWAP", "signal": "ABOVE", "strength": 0.5})
            elif close < vwap * 0.99:
                signals.append({"indicator": "VWAP", "signal": "BELOW", "strength": 0.5})
        
        # Bollinger Bands
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper is not None and bb_lower is not None:
            if close > bb_upper * 0.995:
                signals.append({"indicator": "BB", "signal": "UPPER_TOUCH", "strength": 0.6})
            elif close < bb_lower * 1.005:
                signals.append({"indicator": "BB", "signal": "LOWER_TOUCH", "strength": 0.6})
        
        return signals

    def _combine_signals(self, signals: list, mirofish_data: Optional[dict]) -> tuple:
        """Combine technical signals with MiroFish prediction."""
        # Count technical signals
        bullish_count = sum(1 for s in signals if s["signal"] in ["OVERSOLD", "BULLISH", "ABOVE", "LOWER_TOUCH"])
        bearish_count = sum(1 for s in signals if s["signal"] in ["OVERBOUGHT", "BEARISH", "BELOW", "UPPER_TOUCH"])
        
        # Technical recommendation
        if bullish_count > bearish_count + 1:
            tech_rec = "LONG"
            tech_conf = 0.6 + (bullish_count - bearish_count) * 0.1
        elif bearish_count > bullish_count + 1:
            tech_rec = "SHORT"
            tech_conf = 0.6 + (bearish_count - bullish_count) * 0.1
        else:
            tech_rec = "NEUTRAL"
            tech_conf = 0.5
        
        # Incorporate MiroFish if available
        if mirofish_data:
            miro_bias = mirofish_data.get("directional_bias", "NEUTRAL")
            miro_conf = mirofish_data.get("confidence", 0.5)
            
            # Boost confidence if technical and MiroFish align
            if tech_rec == "LONG" and miro_bias == "BULLISH":
                return "LONG", min(0.95, tech_conf * 0.6 + miro_conf * 0.4)
            elif tech_rec == "SHORT" and miro_bias == "BEARISH":
                return "SHORT", min(0.95, tech_conf * 0.6 + miro_conf * 0.4)
            elif tech_rec == "NEUTRAL" and miro_bias != "NEUTRAL":
                # Follow MiroFish if technical is neutral
                return "LONG" if miro_bias == "BULLISH" else "SHORT", miro_conf * 0.8
            elif tech_rec != "NEUTRAL" and miro_bias == "NEUTRAL":
                # Reduce confidence if MiroFish is neutral
                return tech_rec, tech_conf * 0.7
            elif (tech_rec == "LONG" and miro_bias == "BEARISH") or (tech_rec == "SHORT" and miro_bias == "BULLISH"):
                # Contradiction - reduce confidence significantly
                return "NO_TRADE", 0.4
        
        return tech_rec, min(tech_conf, 0.9)

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
async def run_technical_analysis(
    ticker: str,
    timeframe: str = "5m",
    include_mirofish: bool = True,
) -> dict:
    """Run technical analysis directly."""
    agent = TechnicalAnalysisAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"ta-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="technical_analysis",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
