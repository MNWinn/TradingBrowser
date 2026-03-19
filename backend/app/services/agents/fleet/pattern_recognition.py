"""
Pattern Recognition Agent - Identifies chart patterns.

This agent analyzes price data to identify common chart patterns
including head & shoulders, triangles, double tops/bottoms, etc.
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
class Pattern:
    """Represents a detected chart pattern."""
    name: str
    type: str  # "reversal", "continuation", "bilateral"
    confidence: float
    start_idx: int
    end_idx: int
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    description: str = ""


class PatternRecognitionAgent(BaseAgent):
    """
    Chart pattern recognition specialist.
    
    Specialization:
    - Head & Shoulders (regular and inverse)
    - Double Top / Double Bottom
    - Triangles (ascending, descending, symmetrical)
    - Wedges (rising, falling)
    - Flags and Pennants
    - Channels (parallel, widening)
    - Cup and Handle
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "pattern_recognition",
            agent_type="pattern_recognition",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "chart_pattern_analysis"
        self.min_bars = 30
        self.pattern_types = {
            "head_and_shoulders": {"type": "reversal", "reliability": 0.75},
            "inverse_head_and_shoulders": {"type": "reversal", "reliability": 0.75},
            "double_top": {"type": "reversal", "reliability": 0.70},
            "double_bottom": {"type": "reversal", "reliability": 0.70},
            "ascending_triangle": {"type": "continuation", "reliability": 0.65},
            "descending_triangle": {"type": "continuation", "reliability": 0.65},
            "symmetrical_triangle": {"type": "bilateral", "reliability": 0.60},
            "rising_wedge": {"type": "reversal", "reliability": 0.65},
            "falling_wedge": {"type": "reversal", "reliability": 0.65},
            "bull_flag": {"type": "continuation", "reliability": 0.60},
            "bear_flag": {"type": "continuation", "reliability": 0.60},
            "cup_and_handle": {"type": "continuation", "reliability": 0.70},
        }

    async def _run(self, payload: dict) -> dict:
        """
        Execute pattern recognition analysis.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with detected patterns and confidence scoring
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        
        self.log(f"Starting pattern analysis for {ticker} on {timeframe}", "info")
        
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
                "patterns_detected": [],
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Create DataFrame
        df = self._prepare_data(bars)
        
        # Detect patterns
        patterns = []
        patterns.extend(self._detect_head_and_shoulders(df))
        patterns.extend(self._detect_double_tops_bottoms(df))
        patterns.extend(self._detect_triangles(df))
        patterns.extend(self._detect_wedges(df))
        patterns.extend(self._detect_flags(df))
        patterns.extend(self._detect_cup_and_handle(df))
        
        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        # Calculate overall confidence
        confidence_data = self._calculate_confidence(patterns, df)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(patterns, df)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "patterns_detected": [
                {
                    "name": p.name,
                    "type": p.type,
                    "confidence": round(p.confidence, 3),
                    "price_target": p.price_target,
                    "stop_loss": p.stop_loss,
                    "description": p.description,
                }
                for p in patterns[:5]  # Top 5 patterns
            ],
            "pattern_count": len(patterns),
            "dominant_pattern": patterns[0].name if patterns else None,
            "recommendation": recommendation,
            "confidence": confidence_data["overall_confidence"],
            "confidence_breakdown": confidence_data,
            "price_data": {
                "current": round(df["close"].iloc[-1], 2),
                "high_20d": round(df["high"].tail(20).max(), 2),
                "low_20d": round(df["low"].tail(20).min(), 2),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Pattern analysis complete for {ticker}: {len(patterns)} patterns detected", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _prepare_data(self, bars: list) -> pd.DataFrame:
        """Prepare price data for pattern detection."""
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        
        # Find local extrema
        df["local_high"] = df["high"].rolling(window=5, center=True).max() == df["high"]
        df["local_low"] = df["low"].rolling(window=5, center=True).min() == df["low"]
        
        return df

    def _detect_head_and_shoulders(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect head and shoulders patterns."""
        patterns = []
        highs = df[df["local_high"]].reset_index()
        
        if len(highs) < 3:
            return patterns
        
        # Look for H&S pattern: lower high, higher high, lower high
        for i in range(len(highs) - 2):
            left_shoulder = highs.iloc[i]
            head = highs.iloc[i + 1]
            right_shoulder = highs.iloc[i + 2]
            
            # Check pattern conditions
            head_height = head["high"]
            left_height = left_shoulder["high"]
            right_height = right_shoulder["high"]
            
            # Head should be higher than shoulders
            if head_height > left_height and head_height > right_height:
                # Shoulders should be roughly equal (within 5%)
                shoulder_diff = abs(left_height - right_height) / max(left_height, right_height)
                
                if shoulder_diff < 0.05:
                    # Calculate confidence based on pattern quality
                    confidence = 0.7 - shoulder_diff
                    
                    # Neckline is roughly the low between shoulders
                    neckline_idx = int((left_shoulder["index"] + right_shoulder["index"]) / 2)
                    neckline = df.iloc[neckline_idx]["low"]
                    
                    # Price target: distance from head to neckline projected down
                    pattern_height = head_height - neckline
                    price_target = neckline - pattern_height
                    
                    patterns.append(Pattern(
                        name="head_and_shoulders",
                        type="reversal",
                        confidence=confidence,
                        start_idx=left_shoulder["index"],
                        end_idx=right_shoulder["index"],
                        price_target=round(price_target, 2),
                        stop_loss=round(head_height * 1.02, 2),
                        description=f"Head & Shoulders: Head at {head_height:.2f}, neckline at {neckline:.2f}"
                    ))
        
        # Look for inverse H&S (lows instead of highs)
        lows = df[df["local_low"]].reset_index()
        if len(lows) >= 3:
            for i in range(len(lows) - 2):
                left_shoulder = lows.iloc[i]
                head = lows.iloc[i + 1]
                right_shoulder = lows.iloc[i + 2]
                
                head_depth = head["low"]
                left_depth = left_shoulder["low"]
                right_depth = right_shoulder["low"]
                
                if head_depth < left_depth and head_depth < right_depth:
                    shoulder_diff = abs(left_depth - right_depth) / max(abs(left_depth), abs(right_depth))
                    
                    if shoulder_diff < 0.05:
                        confidence = 0.7 - shoulder_diff
                        
                        neckline_idx = int((left_shoulder["index"] + right_shoulder["index"]) / 2)
                        neckline = df.iloc[neckline_idx]["high"]
                        
                        pattern_height = neckline - head_depth
                        price_target = neckline + pattern_height
                        
                        patterns.append(Pattern(
                            name="inverse_head_and_shoulders",
                            type="reversal",
                            confidence=confidence,
                            start_idx=left_shoulder["index"],
                            end_idx=right_shoulder["index"],
                            price_target=round(price_target, 2),
                            stop_loss=round(head_depth * 0.98, 2),
                            description=f"Inverse Head & Shoulders: Head at {head_depth:.2f}, neckline at {neckline:.2f}"
                        ))
        
        return patterns

    def _detect_double_tops_bottoms(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect double top and double bottom patterns."""
        patterns = []
        
        # Double tops
        highs = df[df["local_high"]].reset_index()
        for i in range(len(highs) - 1):
            first = highs.iloc[i]
            second = highs.iloc[i + 1]
            
            # Peaks should be roughly equal (within 3%)
            diff = abs(first["high"] - second["high"]) / max(first["high"], second["high"])
            
            if diff < 0.03:
                # Find valley between peaks
                valley = df.iloc[first["index"]:second["index"]]["low"].min()
                
                confidence = 0.65 - diff
                pattern_height = first["high"] - valley
                price_target = valley - pattern_height
                
                patterns.append(Pattern(
                    name="double_top",
                    type="reversal",
                    confidence=confidence,
                    start_idx=first["index"],
                    end_idx=second["index"],
                    price_target=round(price_target, 2),
                    stop_loss=round(max(first["high"], second["high"]) * 1.02, 2),
                    description=f"Double Top: Peaks at {first['high']:.2f} and {second['high']:.2f}"
                ))
        
        # Double bottoms
        lows = df[df["local_low"]].reset_index()
        for i in range(len(lows) - 1):
            first = lows.iloc[i]
            second = lows.iloc[i + 1]
            
            diff = abs(first["low"] - second["low"]) / max(abs(first["low"]), abs(second["low"]))
            
            if diff < 0.03:
                peak = df.iloc[first["index"]:second["index"]]["high"].max()
                
                confidence = 0.65 - diff
                pattern_height = peak - first["low"]
                price_target = peak + pattern_height
                
                patterns.append(Pattern(
                    name="double_bottom",
                    type="reversal",
                    confidence=confidence,
                    start_idx=first["index"],
                    end_idx=second["index"],
                    price_target=round(price_target, 2),
                    stop_loss=round(min(first["low"], second["low"]) * 0.98, 2),
                    description=f"Double Bottom: Troughs at {first['low']:.2f} and {second['low']:.2f}"
                ))
        
        return patterns

    def _detect_triangles(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect triangle patterns."""
        patterns = []
        
        # Use last 20 bars for trendline fitting
        recent = df.tail(30)
        if len(recent) < 20:
            return patterns
        
        x = np.arange(len(recent))
        
        # Fit trendlines to highs and lows
        high_slope, high_intercept = np.polyfit(x, recent["high"], 1)
        low_slope, low_intercept = np.polyfit(x, recent["low"], 1)
        
        # Check for convergence (triangle)
        slope_diff = abs(high_slope - low_slope)
        
        # Ascending triangle: flat top, rising bottom
        if abs(high_slope) < 0.001 and low_slope > 0.001:
            patterns.append(Pattern(
                name="ascending_triangle",
                type="continuation",
                confidence=0.65,
                start_idx=len(df) - 30,
                end_idx=len(df) - 1,
                price_target=round(recent["high"].max() + (recent["high"].max() - recent["low"].min()), 2),
                description="Ascending Triangle: Flat resistance with rising support"
            ))
        
        # Descending triangle: falling top, flat bottom
        elif high_slope < -0.001 and abs(low_slope) < 0.001:
            patterns.append(Pattern(
                name="descending_triangle",
                type="continuation",
                confidence=0.65,
                start_idx=len(df) - 30,
                end_idx=len(df) - 1,
                price_target=round(recent["low"].min() - (recent["high"].max() - recent["low"].min()), 2),
                description="Descending Triangle: Falling resistance with flat support"
            ))
        
        # Symmetrical triangle: converging trendlines
        elif high_slope < -0.001 and low_slope > 0.001 and slope_diff < 0.01:
            patterns.append(Pattern(
                name="symmetrical_triangle",
                type="bilateral",
                confidence=0.60,
                start_idx=len(df) - 30,
                end_idx=len(df) - 1,
                description="Symmetrical Triangle: Converging support and resistance"
            ))
        
        return patterns

    def _detect_wedges(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect wedge patterns."""
        patterns = []
        
        recent = df.tail(30)
        if len(recent) < 20:
            return patterns
        
        x = np.arange(len(recent))
        high_slope, _ = np.polyfit(x, recent["high"], 1)
        low_slope, _ = np.polyfit(x, recent["low"], 1)
        
        # Rising wedge: both lines rising, but converging (bearish)
        if high_slope > 0.001 and low_slope > 0.001 and high_slope < low_slope:
            patterns.append(Pattern(
                name="rising_wedge",
                type="reversal",
                confidence=0.65,
                start_idx=len(df) - 30,
                end_idx=len(df) - 1,
                price_target=round(recent["low"].min() - (recent["high"].max() - recent["low"].min()) * 0.5, 2),
                description="Rising Wedge: Converging uptrend lines (bearish reversal)"
            ))
        
        # Falling wedge: both lines falling, but converging (bullish)
        elif high_slope < -0.001 and low_slope < -0.001 and high_slope > low_slope:
            patterns.append(Pattern(
                name="falling_wedge",
                type="reversal",
                confidence=0.65,
                start_idx=len(df) - 30,
                end_idx=len(df) - 1,
                price_target=round(recent["high"].max() + (recent["high"].max() - recent["low"].min()) * 0.5, 2),
                description="Falling Wedge: Converging downtrend lines (bullish reversal)"
            ))
        
        return patterns

    def _detect_flags(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect flag and pennant patterns."""
        patterns = []
        
        # Need at least 40 bars for flag detection
        if len(df) < 40:
            return patterns
        
        # Look for strong move (pole) followed by consolidation
        pole_period = df.iloc[-40:-15]
        consolidation = df.iloc[-15:]
        
        # Calculate pole characteristics
        pole_change = (pole_period["close"].iloc[-1] - pole_period["close"].iloc[0]) / pole_period["close"].iloc[0]
        
        # Strong move > 5%
        if abs(pole_change) > 0.05:
            # Check for consolidation (lower volatility)
            pole_volatility = pole_period["high"].max() - pole_period["low"].min()
            consolidation_range = consolidation["high"].max() - consolidation["low"].min()
            
            if consolidation_range < pole_volatility * 0.5:
                # Bull flag (after up move)
                if pole_change > 0:
                    patterns.append(Pattern(
                        name="bull_flag",
                        type="continuation",
                        confidence=0.60,
                        start_idx=len(df) - 40,
                        end_idx=len(df) - 1,
                        price_target=round(consolidation["close"].iloc[-1] * (1 + abs(pole_change)), 2),
                        description="Bull Flag: Strong up move followed by consolidation"
                    ))
                # Bear flag (after down move)
                else:
                    patterns.append(Pattern(
                        name="bear_flag",
                        type="continuation",
                        confidence=0.60,
                        start_idx=len(df) - 40,
                        end_idx=len(df) - 1,
                        price_target=round(consolidation["close"].iloc[-1] * (1 - abs(pole_change)), 2),
                        description="Bear Flag: Strong down move followed by consolidation"
                    ))
        
        return patterns

    def _detect_cup_and_handle(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect cup and handle patterns."""
        patterns = []
        
        # Need significant lookback
        if len(df) < 60:
            return patterns
        
        # Simplified detection: look for U-shaped recovery
        window = df.tail(60)
        
        # Find lowest point in first half (cup bottom)
        first_half = window.iloc[:30]
        cup_bottom_idx = first_half["low"].idxmin()
        cup_bottom = first_half["low"].min()
        
        # Find high before and after cup
        before_cup = window.loc[:cup_bottom_idx]
        after_cup = window.loc[cup_bottom_idx:]
        
        if len(before_cup) > 10 and len(after_cup) > 10:
            left_rim = before_cup["high"].max()
            right_rim = after_cup["high"].max()
            
            # Rims should be roughly equal
            rim_diff = abs(left_rim - right_rim) / max(left_rim, right_rim)
            
            if rim_diff < 0.05:
                # Check for handle (small pullback from right rim)
                recent = window.tail(10)
                handle_pullback = (right_rim - recent["low"].min()) / right_rim
                
                if 0.02 < handle_pullback < 0.15:  # 2-15% pullback
                    patterns.append(Pattern(
                        name="cup_and_handle",
                        type="continuation",
                        confidence=0.70 - rim_diff,
                        start_idx=len(df) - 60,
                        end_idx=len(df) - 1,
                        price_target=round(right_rim + (right_rim - cup_bottom), 2),
                        description=f"Cup and Handle: Cup depth {right_rim - cup_bottom:.2f}, handle pullback {handle_pullback*100:.1f}%"
                    ))
        
        return patterns

    def _calculate_confidence(self, patterns: List[Pattern], df: pd.DataFrame) -> dict:
        """Calculate overall confidence from detected patterns."""
        if not patterns:
            return {
                "overall_confidence": 0.0,
                "pattern_quality": 0.0,
                "data_quality": 0.5,
            }
        
        # Pattern quality based on top pattern confidence
        pattern_quality = patterns[0].confidence if patterns else 0
        
        # Data quality based on sample size
        data_quality = min(len(df) / 100, 1.0)
        
        # Overall confidence
        overall = pattern_quality * 0.7 + data_quality * 0.3
        
        return {
            "overall_confidence": round(min(overall, 0.95), 3),
            "pattern_quality": round(pattern_quality, 3),
            "data_quality": round(data_quality, 3),
            "patterns_found": len(patterns),
        }

    def _determine_recommendation(self, patterns: List[Pattern], df: pd.DataFrame) -> str:
        """Determine trading recommendation from patterns."""
        if not patterns:
            return "NO_TRADE"
        
        top_pattern = patterns[0]
        
        if top_pattern.confidence < 0.5:
            return "WATCHLIST"
        
        if top_pattern.type == "reversal":
            if "bull" in top_pattern.name or "bottom" in top_pattern.name or "inverse" in top_pattern.name:
                return "LONG"
            else:
                return "SHORT"
        
        elif top_pattern.type == "continuation":
            # Determine trend direction
            trend = df["close"].iloc[-1] > df["close"].iloc[-20]
            if trend:
                return "LONG"
            else:
                return "SHORT"
        
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
async def run_pattern_recognition(
    ticker: str,
    timeframe: str = "5m",
    lookback: int = 100,
) -> dict:
    """Run pattern recognition directly."""
    agent = PatternRecognitionAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"pattern-direct-{ticker}-{datetime.now(timezone.utc).timestamp()}",
        agent_type="pattern_recognition",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "lookback": lookback,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
