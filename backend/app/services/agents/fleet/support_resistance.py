"""
Support/Resistance Agent - Dynamic S/R level detection.

This agent identifies key support and resistance levels using multiple
methods including pivot points, volume profile, and psychological levels.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict, Tuple
from dataclasses import dataclass

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot
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
    Dynamic support and resistance level detection specialist.
    
    Specialization:
    - Pivot point levels (classic, camarilla, woodie)
    - Volume-based S/R levels
    - Psychological levels (round numbers)
    - Fibonacci retracement levels
    - Trendline support/resistance
    - Dynamic level strength scoring
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
        self.specialization = "sr_level_detection"
        self.min_bars = 50

    async def _run(self, payload: dict) -> dict:
        """
        Execute support/resistance analysis.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with detected levels and trading implications
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        
        self.log(f"Starting S/R analysis for {ticker} on {timeframe}", "info")
        
        # Fetch data
        bars_data = get_bars_snapshot(ticker, timeframe=timeframe, limit=lookback)
        bars = bars_data.get("bars", [])
        
        if len(bars) < self.min_bars:
            return {
                "agent": self.agent_type,
                "agent_id": self.agent_id,
                "ticker": ticker,
                "timeframe": timeframe,
                "error": f"Insufficient data: {len(bars)} bars (minimum {self.min_bars} required)",
                "levels": [],
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Detect levels using multiple methods
        levels = []
        levels.extend(self._detect_pivot_levels(df))
        levels.extend(self._detect_volume_levels(df))
        levels.extend(self._detect_psychological_levels(df))
        levels.extend(self._detect_fibonacci_levels(df))
        levels.extend(self._detect_trendline_levels(df))
        
        # Merge and rank levels
        merged_levels = self._merge_levels(levels)
        
        # Sort by strength
        merged_levels.sort(key=lambda l: l.strength, reverse=True)
        
        # Calculate distances and implications
        current_price = df["close"].iloc[-1]
        level_analysis = self._analyze_levels(merged_levels, current_price, df)
        
        # Calculate confidence
        confidence_data = self._calculate_confidence(merged_levels, df)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(level_analysis, current_price)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "levels": [
                {
                    "price": round(l.price, 2),
                    "type": l.type,
                    "strength": round(l.strength, 3),
                    "method": l.method,
                    "touches": l.touches,
                    "description": l.description,
                    "distance_pct": round(abs(l.price - current_price) / current_price * 100, 2),
                }
                for l in merged_levels[:10]  # Top 10 levels
            ],
            "level_analysis": level_analysis,
            "nearest_support": level_analysis.get("nearest_support"),
            "nearest_resistance": level_analysis.get("nearest_resistance"),
            "pivot_point": level_analysis.get("pivot_point"),
            "recommendation": recommendation,
            "confidence": confidence_data["overall_confidence"],
            "confidence_breakdown": confidence_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"S/R analysis complete for {ticker}: {len(merged_levels)} levels detected", "info")
        
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

    def _detect_pivot_levels(self, df: pd.DataFrame) -> List[Level]:
        """Calculate classic pivot point levels."""
        levels = []
        
        # Use last day's data for pivot calculation
        recent = df.tail(20)
        high = recent["high"].max()
        low = recent["low"].min()
        close = recent["close"].iloc[-1]
        
        # Classic pivot
        pivot = (high + low + close) / 3
        
        # Support and resistance levels
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        levels.append(Level(
            price=pivot,
            type="pivot",
            strength=0.8,
            method="pivot",
            touches=1,
            description="Classic Pivot Point"
        ))
        
        levels.append(Level(
            price=r1,
            type="resistance",
            strength=0.6,
            method="pivot",
            touches=1,
            description="Resistance 1 (Classic)"
        ))
        
        levels.append(Level(
            price=r2,
            type="resistance",
            strength=0.5,
            method="pivot",
            touches=1,
            description="Resistance 2 (Classic)"
        ))
        
        levels.append(Level(
            price=s1,
            type="support",
            strength=0.6,
            method="pivot",
            touches=1,
            description="Support 1 (Classic)"
        ))
        
        levels.append(Level(
            price=s2,
            type="support",
            strength=0.5,
            method="pivot",
            touches=1,
            description="Support 2 (Classic)"
        ))
        
        return levels

    def _detect_volume_levels(self, df: pd.DataFrame) -> List[Level]:
        """Detect levels based on volume concentration."""
        levels = []
        
        # Create price bins and sum volume in each
        price_range = df["high"].max() - df["low"].min()
        num_bins = min(20, len(df) // 5)
        
        if num_bins < 5:
            return levels
        
        bin_size = price_range / num_bins
        
        # Calculate volume at each price level
        volume_profile = {}
        for _, row in df.iterrows():
            price_level = round(row["close"] / bin_size) * bin_size
            volume_profile[price_level] = volume_profile.get(price_level, 0) + row["volume"]
        
        # Find high volume nodes
        if volume_profile:
            avg_volume = np.mean(list(volume_profile.values()))
            
            for price, volume in volume_profile.items():
                if volume > avg_volume * 1.5:  # Significant volume concentration
                    strength = min(volume / (avg_volume * 3), 1.0)
                    
                    # Determine if support or resistance based on recent price action
                    current = df["close"].iloc[-1]
                    if price < current:
                        level_type = "support"
                    else:
                        level_type = "resistance"
                    
                    levels.append(Level(
                        price=price,
                        type=level_type,
                        strength=strength * 0.7,  # Volume levels slightly less reliable
                        method="volume",
                        touches=int(volume / avg_volume),
                        description=f"High Volume Node ({int(volume/avg_volume)}x avg)"
                    ))
        
        return levels

    def _detect_psychological_levels(self, df: pd.DataFrame) -> List[Level]:
        """Detect psychological round number levels."""
        levels = []
        
        current_price = df["close"].iloc[-1]
        
        # Determine appropriate rounding based on price magnitude
        if current_price < 10:
            step = 0.5
        elif current_price < 100:
            step = 1.0
        elif current_price < 500:
            step = 5.0
        else:
            step = 10.0
        
        # Generate nearby psychological levels
        base = round(current_price / step) * step
        
        for offset in [-2, -1, 0, 1, 2]:
            level_price = base + (offset * step)
            if level_price > 0:
                # Count how many times price approached this level
                touches = sum(
                    1 for _, row in df.iterrows()
                    if abs(row["close"] - level_price) / level_price < 0.01
                )
                
                if touches > 0 or abs(offset) <= 1:  # Include nearby levels even if not touched
                    level_type = "support" if level_price < current_price else "resistance"
                    
                    levels.append(Level(
                        price=level_price,
                        type=level_type,
                        strength=0.4 + (0.1 * min(touches, 3)),  # Base strength + touches
                        method="psychological",
                        touches=touches,
                        description=f"Psychological Level ({step} step)"
                    ))
        
        return levels

    def _detect_fibonacci_levels(self, df: pd.DataFrame) -> List[Level]:
        """Calculate Fibonacci retracement levels."""
        levels = []
        
        # Find significant swing high and low
        recent = df.tail(50)
        swing_high = recent["high"].max()
        swing_low = recent["low"].min()
        
        if swing_high == swing_low:
            return levels
        
        range_size = swing_high - swing_low
        
        # Fibonacci ratios
        fib_ratios = {
            0.236: "23.6%",
            0.382: "38.2%",
            0.5: "50%",
            0.618: "61.8%",
            0.786: "78.6%",
        }
        
        for ratio, label in fib_ratios.items():
            level_price = swing_high - (range_size * ratio)
            
            # Count touches
            touches = sum(
                1 for _, row in df.iterrows()
                if abs(row["close"] - level_price) / level_price < 0.005
            )
            
            # Determine type based on current price
            current = df["close"].iloc[-1]
            level_type = "support" if level_price < current else "resistance"
            
            # Strength based on ratio importance and touches
            base_strength = 0.5 if ratio in [0.382, 0.5, 0.618] else 0.4
            strength = base_strength + (0.1 * min(touches, 2))
            
            levels.append(Level(
                price=level_price,
                type=level_type,
                strength=min(strength, 0.9),
                method="fibonacci",
                touches=touches,
                description=f"Fibonacci {label} Retracement"
            ))
        
        return levels

    def _detect_trendline_levels(self, df: pd.DataFrame) -> List[Level]:
        """Detect dynamic trendline support/resistance."""
        levels = []
        
        recent = df.tail(30)
        if len(recent) < 20:
            return levels
        
        x = np.arange(len(recent))
        
        # Fit trendline to highs (resistance)
        high_slope, high_intercept = np.polyfit(x, recent["high"], 1)
        
        # Fit trendline to lows (support)
        low_slope, low_intercept = np.polyfit(x, recent["low"], 1)
        
        # Project forward
        next_x = len(recent)
        
        # Resistance trendline
        resistance_price = high_slope * next_x + high_intercept
        
        # Support trendline
        support_price = low_slope * next_x + low_intercept
        
        # Check trend quality (R-squared approximation)
        high_fit = np.corrcoef(x, recent["high"])[0, 1] ** 2
        low_fit = np.corrcoef(x, recent["low"])[0, 1] ** 2
        
        if not np.isnan(high_fit) and high_fit > 0.5:
            levels.append(Level(
                price=resistance_price,
                type="resistance",
                strength=min(high_fit * 0.8, 0.85),
                method="trendline",
                touches=3,
                description=f"Dynamic Resistance Trendline (slope: {high_slope:.4f})"
            ))
        
        if not np.isnan(low_fit) and low_fit > 0.5:
            levels.append(Level(
                price=support_price,
                type="support",
                strength=min(low_fit * 0.8, 0.85),
                method="trendline",
                touches=3,
                description=f"Dynamic Support Trendline (slope: {low_slope:.4f})"
            ))
        
        return levels

    def _merge_levels(self, levels: List[Level]) -> List[Level]:
        """Merge nearby levels and combine strengths."""
        if not levels:
            return levels
        
        # Sort by price
        levels.sort(key=lambda l: l.price)
        
        merged = []
        current_group = [levels[0]]
        
        for level in levels[1:]:
            # Check if level is close to current group (within 1%)
            group_avg = np.mean([l.price for l in current_group])
            if abs(level.price - group_avg) / group_avg < 0.01:
                current_group.append(level)
            else:
                # Merge current group
                merged.append(self._combine_levels(current_group))
                current_group = [level]
        
        # Don't forget the last group
        if current_group:
            merged.append(self._combine_levels(current_group))
        
        return merged

    def _combine_levels(self, levels: List[Level]) -> Level:
        """Combine multiple levels into one."""
        # Weighted average price by strength
        total_weight = sum(l.strength for l in levels)
        avg_price = sum(l.price * l.strength for l in levels) / total_weight
        
        # Combined strength (capped)
        combined_strength = min(sum(l.strength for l in levels) / len(levels) * 1.2, 1.0)
        
        # Total touches
        total_touches = sum(l.touches for l in levels)
        
        # Determine dominant type
        support_count = sum(1 for l in levels if l.type == "support")
        resistance_count = sum(1 for l in levels if l.type == "resistance")
        dominant_type = "support" if support_count > resistance_count else "resistance"
        
        # Combine methods
        methods = ", ".join(set(l.method for l in levels))
        
        return Level(
            price=avg_price,
            type=dominant_type,
            strength=combined_strength,
            method="combined",
            touches=total_touches,
            description=f"Combined Level ({methods})"
        )

    def _analyze_levels(self, levels: List[Level], current_price: float, df: pd.DataFrame) -> dict:
        """Analyze levels relative to current price."""
        analysis = {
            "total_levels": len(levels),
            "support_levels": len([l for l in levels if l.type == "support"]),
            "resistance_levels": len([l for l in levels if l.type == "resistance"]),
        }
        
        # Find nearest support and resistance
        supports = [l for l in levels if l.type == "support" and l.price < current_price]
        resistances = [l for l in levels if l.type == "resistance" and l.price > current_price]
        
        if supports:
            nearest_support = max(supports, key=lambda l: l.price)
            analysis["nearest_support"] = {
                "price": round(nearest_support.price, 2),
                "distance_pct": round((current_price - nearest_support.price) / current_price * 100, 2),
                "strength": round(nearest_support.strength, 3),
            }
        
        if resistances:
            nearest_resistance = min(resistances, key=lambda l: l.price)
            analysis["nearest_resistance"] = {
                "price": round(nearest_resistance.price, 2),
                "distance_pct": round((nearest_resistance.price - current_price) / current_price * 100, 2),
                "strength": round(nearest_resistance.strength, 3),
            }
        
        # Find pivot point if exists
        pivots = [l for l in levels if l.type == "pivot"]
        if pivots:
            analysis["pivot_point"] = round(pivots[0].price, 2)
        
        # Price position relative to levels
        if supports and resistances:
            range_size = nearest_resistance.price - nearest_support.price
            position_in_range = (current_price - nearest_support.price) / range_size
            analysis["position_in_range"] = round(position_in_range, 3)
        
        return analysis

    def _calculate_confidence(self, levels: List[Level], df: pd.DataFrame) -> dict:
        """Calculate overall confidence."""
        if not levels:
            return {
                "overall_confidence": 0.0,
                "level_quality": 0.0,
                "data_quality": 0.5,
            }
        
        # Level quality based on average strength
        level_quality = np.mean([l.strength for l in levels])
        
        # Data quality
        data_quality = min(len(df) / 100, 1.0)
        
        # Level count bonus (more levels = more confidence, up to a point)
        count_bonus = min(len(levels) / 10, 0.2)
        
        overall = (level_quality * 0.5 + data_quality * 0.3 + count_bonus)
        
        return {
            "overall_confidence": round(min(overall, 0.95), 3),
            "level_quality": round(level_quality, 3),
            "data_quality": round(data_quality, 3),
            "level_count": len(levels),
        }

    def _determine_recommendation(self, analysis: dict, current_price: float) -> str:
        """Determine trading recommendation based on level analysis."""
        nearest_support = analysis.get("nearest_support")
        nearest_resistance = analysis.get("nearest_resistance")
        position = analysis.get("position_in_range")
        
        if not nearest_support or not nearest_resistance:
            return "WATCHLIST"
        
        # Close to support with strong level
        if nearest_support["distance_pct"] < 1.0 and nearest_support["strength"] > 0.6:
            return "LONG"
        
        # Close to resistance with strong level
        if nearest_resistance["distance_pct"] < 1.0 and nearest_resistance["strength"] > 0.6:
            return "SHORT"
        
        # Mid-range
        if position and 0.3 < position < 0.7:
            return "WATCHLIST"
        
        # Near support but not too close
        if nearest_support["distance_pct"] < 3.0:
            return "WATCHLIST_LONG"
        
        # Near resistance but not too close
        if nearest_resistance["distance_pct"] < 3.0:
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
async def run_support_resistance_analysis(
    ticker: str,
    timeframe: str = "5m",
    lookback: int = 100,
) -> dict:
    """Run S/R analysis directly."""
    agent = SupportResistanceAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"sr-direct-{ticker}-{datetime.now(timezone.utc).timestamp()}",
        agent_type="support_resistance",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "lookback": lookback,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
