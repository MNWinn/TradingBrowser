"""
Support/Resistance Agent with MiroFish Levels

This agent identifies S/R levels and uses MiroFish predictions
to validate level significance and trading implications.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict
from dataclasses import dataclass

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot
from app.services.agents.fleet.mirofish_assessment import run_mirofish_assessment
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


@dataclass
class Level:
    """Represents a support/resistance level."""
    price: float
    type: str  # "support", "resistance", "pivot"
    strength: float  # 0-1
    method: str  # "pivot", "volume", "psychological", "fibonacci"
    touches: int
    description: str


class SupportResistanceAgent(BaseAgent):
    """
    Support/Resistance detection with MiroFish level validation.
    
    Specialization:
    - Dynamic S/R level detection
    - MiroFish-validated significant levels
    - Price proximity analysis with AI context
    - Breakout/breakdown prediction
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "support_resistance",
            agent_type="support_resistance",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "sr_analysis_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute S/R analysis with MiroFish validation.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with S/R levels and MiroFish-enhanced trading implications
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
        self.log(f"Starting S/R analysis for {ticker} on {timeframe}", "info")
        
        # Fetch data
        bars_data = get_bars_snapshot(ticker, timeframe=timeframe, limit=lookback)
        bars = bars_data.get("bars", [])
        
        if len(bars) < 50:
            return {
                "agent": self.agent_type,
                "agent_id": self.agent_id,
                "ticker": ticker,
                "timeframe": timeframe,
                "error": f"Insufficient data: {len(bars)} bars (minimum 50 required)",
                "levels": [],
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Detect levels
        levels = self._detect_levels(df)
        
        # Get MiroFish context
        mirofish_data = None
        if include_mirofish:
            try:
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
            except Exception as e:
                self.log(f"MiroFish context failed: {e}", "warning")
        
        # Enhance levels with MiroFish
        enhanced_levels = self._enhance_levels_with_mirofish(levels, mirofish_data, df["close"].iloc[-1])
        
        # Generate recommendation
        recommendation, confidence = self._generate_recommendation(enhanced_levels, df, mirofish_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "levels": [self._level_to_dict(l) for l in enhanced_levels],
            "level_count": len(enhanced_levels),
            "current_price": round(df["close"].iloc[-1], 2),
            "recommendation": recommendation,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"S/R analysis complete for {ticker}: {len(enhanced_levels)} levels detected", "info")
        
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

    def _detect_levels(self, df: pd.DataFrame) -> List[Level]:
        """Detect support and resistance levels."""
        levels = []
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        
        # Find pivot highs and lows
        window = 3
        pivot_highs = []
        pivot_lows = []
        
        for i in range(window, len(high) - window):
            # Pivot high
            if high[i] == max(high[i-window:i+window+1]):
                pivot_highs.append((i, high[i]))
            # Pivot low
            if low[i] == min(low[i-window:i+window+1]):
                pivot_lows.append((i, low[i]))
        
        # Group similar levels (within 1%)
        resistance_levels = self._cluster_levels(pivot_highs, threshold=0.01)
        support_levels = self._cluster_levels(pivot_lows, threshold=0.01)
        
        # Create Level objects
        for price, touches in resistance_levels:
            strength = min(0.9, 0.4 + touches * 0.15)
            levels.append(Level(
                price=round(price, 2),
                type="resistance",
                strength=round(strength, 2),
                method="pivot",
                touches=touches,
                description=f"Resistance level with {touches} touches"
            ))
        
        for price, touches in support_levels:
            strength = min(0.9, 0.4 + touches * 0.15)
            levels.append(Level(
                price=round(price, 2),
                type="support",
                strength=round(strength, 2),
                method="pivot",
                touches=touches,
                description=f"Support level with {touches} touches"
            ))
        
        # Add psychological levels (round numbers)
        current_price = close[-1]
        for level in np.arange(round(current_price / 10) * 10 - 50, round(current_price / 10) * 10 + 60, 10):
            if abs(level - current_price) / current_price < 0.1:
                levels.append(Level(
                    price=round(level, 2),
                    type="pivot",
                    strength=0.5,
                    method="psychological",
                    touches=0,
                    description=f"Psychological level at {level}"
                ))
        
        return levels

    def _cluster_levels(self, pivots: List[tuple], threshold: float) -> List[tuple]:
        """Cluster similar price levels."""
        if not pivots:
            return []
        
        clusters = []
        prices = [p[1] for p in pivots]
        
        for price in prices:
            found = False
            for i, (cluster_price, count) in enumerate(clusters):
                if abs(price - cluster_price) / cluster_price < threshold:
                    clusters[i] = ((cluster_price * count + price) / (count + 1), count + 1)
                    found = True
                    break
            if not found:
                clusters.append((price, 1))
        
        return clusters

    def _enhance_levels_with_mirofish(self, levels: List[Level], mirofish_data: Optional[dict], current_price: float) -> List[Level]:
        """Enhance level significance using MiroFish context."""
        if not mirofish_data:
            return levels
        
        bias = mirofish_data.get("directional_bias", "NEUTRAL")
        confidence = mirofish_data.get("confidence", 0.5)
        
        enhanced = []
        for level in levels:
            new_strength = level.strength
            
            # Adjust strength based on MiroFish bias and level type
            if bias == "BULLISH":
                if level.type == "support":
                    # Support more significant in bullish context
                    new_strength = min(0.95, level.strength + confidence * 0.1)
                elif level.type == "resistance":
                    # Resistance may be broken in bullish context
                    new_strength = max(0.1, level.strength - confidence * 0.1)
            elif bias == "BEARISH":
                if level.type == "resistance":
                    # Resistance more significant in bearish context
                    new_strength = min(0.95, level.strength + confidence * 0.1)
                elif level.type == "support":
                    # Support may be broken in bearish context
                    new_strength = max(0.1, level.strength - confidence * 0.1)
            
            # Check proximity to current price
            distance = abs(level.price - current_price) / current_price
            if distance < 0.01:  # Within 1%
                new_strength = min(0.95, new_strength + 0.1)
            
            enhanced.append(Level(
                price=level.price,
                type=level.type,
                strength=round(new_strength, 2),
                method=level.method,
                touches=level.touches,
                description=level.description
            ))
        
        # Sort by strength
        enhanced.sort(key=lambda x: x.strength, reverse=True)
        return enhanced[:10]  # Return top 10 levels

    def _generate_recommendation(self, levels: List[Level], df: pd.DataFrame, mirofish_data: Optional[dict]) -> tuple:
        """Generate trading recommendation based on S/R levels."""
        current_price = df["close"].iloc[-1]
        
        # Find nearest support and resistance
        supports = [l for l in levels if l.type == "support"]
        resistances = [l for l in levels if l.type == "resistance"]
        
        nearest_support = max(supports, key=lambda x: x.price) if supports and max(s.price for s in supports) < current_price else None
        nearest_resistance = min(resistances, key=lambda x: x.price) if resistances and min(r.price for r in resistances) > current_price else None
        
        if not nearest_support and not nearest_resistance:
            return "NEUTRAL", 0.5
        
        # Calculate distance to levels
        support_distance = (current_price - nearest_support.price) / current_price if nearest_support else 1.0
        resistance_distance = (nearest_resistance.price - current_price) / current_price if nearest_resistance else 1.0
        
        # Base recommendation on proximity
        if support_distance < 0.01 and nearest_support and nearest_support.strength > 0.6:
            base_rec = "LONG"
            base_conf = nearest_support.strength
        elif resistance_distance < 0.01 and nearest_resistance and nearest_resistance.strength > 0.6:
            base_rec = "SHORT"
            base_conf = nearest_resistance.strength
        elif support_distance < resistance_distance:
            base_rec = "LONG"
            base_conf = 0.5
        else:
            base_rec = "SHORT"
            base_conf = 0.5
        
        # Incorporate MiroFish
        if mirofish_data:
            bias = mirofish_data.get("directional_bias", "NEUTRAL")
            miro_conf = mirofish_data.get("confidence", 0.5)
            
            if base_rec == "LONG" and bias == "BULLISH":
                return "LONG", min(0.95, base_conf * 0.6 + miro_conf * 0.4)
            elif base_rec == "SHORT" and bias == "BEARISH":
                return "SHORT", min(0.95, base_conf * 0.6 + miro_conf * 0.4)
            elif bias != "NEUTRAL":
                return "LONG" if bias == "BULLISH" else "SHORT", miro_conf * 0.7
        
        return base_rec, base_conf

    def _level_to_dict(self, level: Level) -> dict:
        """Convert level to dictionary."""
        return {
            "price": level.price,
            "type": level.type,
            "strength": level.strength,
            "method": level.method,
            "touches": level.touches,
            "description": level.description,
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
async def run_support_resistance_analysis(
    ticker: str,
    timeframe: str = "5m",
    include_mirofish: bool = True,
) -> dict:
    """Run S/R analysis directly."""
    agent = SupportResistanceAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"sr-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="support_resistance",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
