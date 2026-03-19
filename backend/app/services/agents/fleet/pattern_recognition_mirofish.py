"""
Pattern Recognition Agent with MiroFish Context

This agent identifies chart patterns and uses MiroFish context
to enhance pattern reliability scoring.
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
    Pattern recognition with MiroFish context.
    
    Specialization:
    - Chart pattern detection with MiroFish confirmation
    - Pattern reliability scoring using AI predictions
    - Multi-timeframe pattern analysis
    - Context-aware pattern filtering
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
        self.specialization = "pattern_analysis_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute pattern recognition with MiroFish context.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with detected patterns and MiroFish-enhanced confidence
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
        self.log(f"Starting pattern analysis for {ticker} on {timeframe}", "info")
        
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
                "patterns": [],
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Detect patterns
        patterns = self._detect_patterns(df)
        
        # Get MiroFish context
        mirofish_data = None
        if include_mirofish:
            try:
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
            except Exception as e:
                self.log(f"MiroFish context failed: {e}", "warning")
        
        # Enhance patterns with MiroFish context
        enhanced_patterns = self._enhance_patterns_with_mirofish(patterns, mirofish_data)
        
        # Generate recommendation
        recommendation, confidence = self._generate_recommendation(enhanced_patterns, mirofish_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "patterns": [self._pattern_to_dict(p) for p in enhanced_patterns],
            "pattern_count": len(enhanced_patterns),
            "recommendation": recommendation,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Pattern analysis complete for {ticker}: {len(enhanced_patterns)} patterns detected", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _prepare_data(self, bars: list) -> pd.DataFrame:
        """Prepare price data for pattern detection."""
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df

    def _detect_patterns(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect chart patterns in price data."""
        patterns = []
        
        # Detect double top/bottom
        patterns.extend(self._detect_double_patterns(df))
        
        # Detect triangles
        patterns.extend(self._detect_triangles(df))
        
        # Detect support/resistance breaks
        patterns.extend(self._detect_breakouts(df))
        
        return patterns

    def _detect_double_patterns(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect double top and double bottom patterns."""
        patterns = []
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        
        if len(close) < 20:
            return patterns
        
        # Find local extrema
        window = 5
        
        # Double Top detection
        for i in range(window + 5, len(high) - window - 5):
            # Find local highs
            if high[i] == max(high[i-window:i+window+1]):
                # Look for similar high after pullback
                for j in range(i + 5, min(i + 20, len(high) - window)):
                    if high[j] == max(high[j-window:j+window+1]):
                        # Check if highs are similar (within 2%)
                        if abs(high[i] - high[j]) / high[i] < 0.02:
                            # Check for pullback between
                            pullback = min(low[i:j])
                            if pullback < high[i] * 0.98:
                                patterns.append(Pattern(
                                    name="Double Top",
                                    type="reversal",
                                    confidence=0.65,
                                    start_idx=i,
                                    end_idx=j,
                                    price_target=round(pullback - (high[i] - pullback), 2),
                                    stop_loss=round(max(high[i], high[j]) * 1.01, 2),
                                    description=f"Double top pattern detected between bars {i} and {j}"
                                ))
        
        # Double Bottom detection
        for i in range(window + 5, len(low) - window - 5):
            if low[i] == min(low[i-window:i+window+1]):
                for j in range(i + 5, min(i + 20, len(low) - window)):
                    if low[j] == min(low[j-window:j+window+1]):
                        if abs(low[i] - low[j]) / low[i] < 0.02:
                            rally = max(high[i:j])
                            if rally > low[i] * 1.02:
                                patterns.append(Pattern(
                                    name="Double Bottom",
                                    type="reversal",
                                    confidence=0.65,
                                    start_idx=i,
                                    end_idx=j,
                                    price_target=round(rally + (rally - low[i]), 2),
                                    stop_loss=round(min(low[i], low[j]) * 0.99, 2),
                                    description=f"Double bottom pattern detected between bars {i} and {j}"
                                ))
        
        return patterns

    def _detect_triangles(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect triangle patterns."""
        patterns = []
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        
        if len(close) < 30:
            return patterns
        
        # Look for converging highs and lows
        lookback = 20
        
        # Calculate trend lines
        x = np.arange(lookback)
        high_slope = np.polyfit(x, high[-lookback:], 1)[0]
        low_slope = np.polyfit(x, low[-lookback:], 1)[0]
        
        # Symmetrical triangle: converging trend lines
        if high_slope < -0.01 and low_slope > 0.01:
            patterns.append(Pattern(
                name="Symmetrical Triangle",
                type="bilateral",
                confidence=0.55,
                start_idx=len(close) - lookback,
                end_idx=len(close) - 1,
                price_target=round(close[-1] + (high[-1] - low[-1]), 2),
                stop_loss=round(low[-1] * 0.98, 2),
                description="Symmetrical triangle pattern detected"
            ))
        
        # Ascending triangle: flat top, rising bottom
        if abs(high_slope) < 0.005 and low_slope > 0.01:
            patterns.append(Pattern(
                name="Ascending Triangle",
                type="continuation",
                confidence=0.60,
                start_idx=len(close) - lookback,
                end_idx=len(close) - 1,
                price_target=round(high[-1] + (high[-1] - low[-1]), 2),
                stop_loss=round(low[-1] * 0.98, 2),
                description="Ascending triangle pattern detected (bullish)"
            ))
        
        # Descending triangle: flat bottom, falling top
        if abs(low_slope) < 0.005 and high_slope < -0.01:
            patterns.append(Pattern(
                name="Descending Triangle",
                type="continuation",
                confidence=0.60,
                start_idx=len(close) - lookback,
                end_idx=len(close) - 1,
                price_target=round(low[-1] - (high[-1] - low[-1]), 2),
                stop_loss=round(high[-1] * 1.02, 2),
                description="Descending triangle pattern detected (bearish)"
            ))
        
        return patterns

    def _detect_breakouts(self, df: pd.DataFrame) -> List[Pattern]:
        """Detect support/resistance breakouts."""
        patterns = []
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        
        if len(close) < 20:
            return patterns
        
        # Calculate recent range
        recent_high = max(high[-20:-1])
        recent_low = min(low[-20:-1])
        
        # Breakout above resistance
        if close[-1] > recent_high * 1.01:
            patterns.append(Pattern(
                name="Resistance Breakout",
                type="continuation",
                confidence=0.60,
                start_idx=len(close) - 20,
                end_idx=len(close) - 1,
                price_target=round(close[-1] + (recent_high - recent_low) * 0.5, 2),
                stop_loss=round(recent_high * 0.99, 2),
                description=f"Price broke above resistance at {round(recent_high, 2)}"
            ))
        
        # Breakdown below support
        if close[-1] < recent_low * 0.99:
            patterns.append(Pattern(
                name="Support Breakdown",
                type="reversal",
                confidence=0.60,
                start_idx=len(close) - 20,
                end_idx=len(close) - 1,
                price_target=round(close[-1] - (recent_high - recent_low) * 0.5, 2),
                stop_loss=round(recent_low * 1.01, 2),
                description=f"Price broke below support at {round(recent_low, 2)}"
            ))
        
        return patterns

    def _enhance_patterns_with_mirofish(self, patterns: List[Pattern], mirofish_data: Optional[dict]) -> List[Pattern]:
        """Enhance pattern confidence using MiroFish context."""
        if not mirofish_data:
            return patterns
        
        bias = mirofish_data.get("directional_bias", "NEUTRAL")
        miro_conf = mirofish_data.get("confidence", 0.5)
        
        enhanced = []
        for pattern in patterns:
            new_confidence = pattern.confidence
            
            # Boost confidence if pattern aligns with MiroFish bias
            if pattern.type == "reversal":
                if pattern.name in ["Double Bottom", "Inverse Head and Shoulders"] and bias == "BULLISH":
                    new_confidence = min(0.95, pattern.confidence + miro_conf * 0.2)
                elif pattern.name in ["Double Top", "Head and Shoulders"] and bias == "BEARISH":
                    new_confidence = min(0.95, pattern.confidence + miro_conf * 0.2)
            
            elif pattern.type == "continuation":
                if pattern.name in ["Ascending Triangle", "Bull Flag", "Resistance Breakout"] and bias == "BULLISH":
                    new_confidence = min(0.95, pattern.confidence + miro_conf * 0.2)
                elif pattern.name in ["Descending Triangle", "Bear Flag", "Support Breakdown"] and bias == "BEARISH":
                    new_confidence = min(0.95, pattern.confidence + miro_conf * 0.2)
            
            enhanced.append(Pattern(
                name=pattern.name,
                type=pattern.type,
                confidence=round(new_confidence, 2),
                start_idx=pattern.start_idx,
                end_idx=pattern.end_idx,
                price_target=pattern.price_target,
                stop_loss=pattern.stop_loss,
                description=pattern.description
            ))
        
        return enhanced

    def _generate_recommendation(self, patterns: List[Pattern], mirofish_data: Optional[dict]) -> tuple:
        """Generate trading recommendation from patterns."""
        if not patterns:
            return "NO_TRADE", 0.0
        
        # Get highest confidence patterns
        bullish_patterns = [p for p in patterns if p.type in ["continuation", "reversal"] and 
                          ("Bottom" in p.name or "Ascending" in p.name or "Breakout" in p.name)]
        bearish_patterns = [p for p in patterns if p.type in ["continuation", "reversal"] and 
                          ("Top" in p.name or "Descending" in p.name or "Breakdown" in p.name)]
        
        # Calculate weighted confidence
        bullish_conf = sum(p.confidence for p in bullish_patterns) / len(bullish_patterns) if bullish_patterns else 0
        bearish_conf = sum(p.confidence for p in bearish_patterns) / len(bearish_patterns) if bearish_patterns else 0
        
        # Incorporate MiroFish
        if mirofish_data:
            bias = mirofish_data.get("directional_bias", "NEUTRAL")
            miro_conf = mirofish_data.get("confidence", 0.5)
            
            if bias == "BULLISH":
                bullish_conf = bullish_conf * 0.6 + miro_conf * 0.4
            elif bias == "BEARISH":
                bearish_conf = bearish_conf * 0.6 + miro_conf * 0.4
        
        if bullish_conf > bearish_conf and bullish_conf > 0.5:
            return "LONG", round(min(bullish_conf, 0.95), 2)
        elif bearish_conf > bullish_conf and bearish_conf > 0.5:
            return "SHORT", round(min(bearish_conf, 0.95), 2)
        else:
            return "NEUTRAL", 0.5

    def _pattern_to_dict(self, pattern: Pattern) -> dict:
        """Convert pattern to dictionary."""
        return {
            "name": pattern.name,
            "type": pattern.type,
            "confidence": pattern.confidence,
            "price_target": pattern.price_target,
            "stop_loss": pattern.stop_loss,
            "description": pattern.description,
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
async def run_pattern_recognition(
    ticker: str,
    timeframe: str = "5m",
    include_mirofish: bool = True,
) -> dict:
    """Run pattern recognition directly."""
    agent = PatternRecognitionAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"pattern-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="pattern_recognition",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
