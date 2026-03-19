"""
Volume Profile Agent with MiroFish Volume Analysis

This agent analyzes volume profiles and uses MiroFish predictions
to validate volume-based trading signals.
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
class VolumeNode:
    """Represents a volume concentration at a price level."""
    price_level: float
    volume: float
    relative_volume: float
    bar_count: int
    type: str  # "poc", "value_area", "low_volume", "single_print"


class VolumeProfileAgent(BaseAgent):
    """
    Volume profile analysis with MiroFish volume validation.
    
    Specialization:
    - Volume profile construction
    - Point of Control (POC) identification
    - Value Area analysis with MiroFish context
    - Volume-based signal confirmation
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "volume_profile",
            agent_type="volume_profile",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "volume_analysis_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute volume profile analysis with MiroFish validation.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with volume profile and MiroFish-enhanced signals
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
        self.log(f"Starting volume profile analysis for {ticker} on {timeframe}", "info")
        
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
        
        # Build volume profile
        profile = self._build_volume_profile(df)
        
        # Get MiroFish context
        mirofish_data = None
        if include_mirofish:
            try:
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
            except Exception as e:
                self.log(f"MiroFish context failed: {e}", "warning")
        
        # Generate recommendation
        recommendation, confidence = self._generate_recommendation(profile, df, mirofish_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "volume_profile": self._profile_to_dict(profile),
            "current_price": round(df["close"].iloc[-1], 2),
            "recommendation": recommendation,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Volume profile analysis complete for {ticker}: POC at {profile['poc']}", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _prepare_data(self, bars: list) -> pd.DataFrame:
        """Prepare price and volume data."""
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df

    def _build_volume_profile(self, df: pd.DataFrame) -> Dict:
        """Build volume profile from price and volume data."""
        close = df["close"].values
        volume = df["volume"].values
        high = df["high"].values
        low = df["low"].values
        
        # Create price bins
        num_bins = 24
        min_price = min(low)
        max_price = max(high)
        bin_size = (max_price - min_price) / num_bins
        
        # Calculate volume per bin
        bins = np.linspace(min_price, max_price, num_bins + 1)
        volume_profile = np.zeros(num_bins)
        
        for i in range(len(close)):
            # Distribute volume across price range of the bar
            bar_low = low[i]
            bar_high = high[i]
            bar_volume = volume[i]
            
            for j in range(num_bins):
                bin_low = bins[j]
                bin_high = bins[j + 1]
                
                # Calculate overlap
                overlap_low = max(bar_low, bin_low)
                overlap_high = min(bar_high, bin_high)
                
                if overlap_high > overlap_low:
                    overlap_ratio = (overlap_high - overlap_low) / (bar_high - bar_low) if bar_high > bar_low else 1
                    volume_profile[j] += bar_volume * overlap_ratio
        
        # Find Point of Control (POC)
        poc_idx = np.argmax(volume_profile)
        poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2
        
        # Calculate Value Area (70% of volume)
        total_volume = np.sum(volume_profile)
        target_volume = total_volume * 0.70
        
        # Start from POC and expand
        value_area_idx = [poc_idx]
        current_volume = volume_profile[poc_idx]
        
        left_idx = poc_idx - 1
        right_idx = poc_idx + 1
        
        while current_volume < target_volume and (left_idx >= 0 or right_idx < num_bins):
            left_vol = volume_profile[left_idx] if left_idx >= 0 else 0
            right_vol = volume_profile[right_idx] if right_idx < num_bins else 0
            
            if left_vol >= right_vol and left_idx >= 0:
                value_area_idx.append(left_idx)
                current_volume += left_vol
                left_idx -= 1
            elif right_idx < num_bins:
                value_area_idx.append(right_idx)
                current_volume += right_vol
                right_idx += 1
            else:
                break
        
        value_area_low = bins[min(value_area_idx)]
        value_area_high = bins[max(value_area_idx) + 1]
        
        # Create volume nodes
        nodes = []
        for i in range(num_bins):
            if volume_profile[i] > 0:
                price_level = (bins[i] + bins[i + 1]) / 2
                rel_volume = volume_profile[i] / np.mean(volume_profile)
                
                if i == poc_idx:
                    node_type = "poc"
                elif i in value_area_idx:
                    node_type = "value_area"
                elif rel_volume < 0.5:
                    node_type = "low_volume"
                else:
                    node_type = "normal"
                
                nodes.append(VolumeNode(
                    price_level=round(price_level, 2),
                    volume=round(volume_profile[i], 2),
                    relative_volume=round(rel_volume, 2),
                    bar_count=int(volume_profile[i] / np.mean(volume)),
                    type=node_type
                ))
        
        return {
            "poc": round(poc_price, 2),
            "value_area_high": round(value_area_high, 2),
            "value_area_low": round(value_area_low, 2),
            "value_area_volume_pct": round(current_volume / total_volume * 100, 1),
            "total_volume": round(total_volume, 2),
            "nodes": nodes,
            "profile_shape": self._classify_profile_shape(volume_profile),
        }

    def _classify_profile_shape(self, volume_profile: np.ndarray) -> str:
        """Classify the shape of the volume profile."""
        if len(volume_profile) < 3:
            return "insufficient_data"
        
        # Find peaks
        poc_idx = np.argmax(volume_profile)
        
        # Check distribution
        left_volume = np.sum(volume_profile[:poc_idx]) if poc_idx > 0 else 0
        right_volume = np.sum(volume_profile[poc_idx+1:]) if poc_idx < len(volume_profile) - 1 else 0
        
        # Classify shape
        if volume_profile[poc_idx] > np.mean(volume_profile) * 2:
            if abs(left_volume - right_volume) / max(left_volume, right_volume, 1) < 0.2:
                return "d"  # Balanced distribution
            elif left_volume > right_volume:
                return "p"  # Skewed to higher prices
            else:
                return "b"  # Skewed to lower prices
        else:
            return "thin"  # Flat profile

    def _generate_recommendation(self, profile: Dict, df: pd.DataFrame, mirofish_data: Optional[dict]) -> tuple:
        """Generate trading recommendation from volume profile."""
        current_price = df["close"].iloc[-1]
        poc = profile["poc"]
        va_high = profile["value_area_high"]
        va_low = profile["value_area_low"]
        
        # Determine position relative to value area
        if current_price > va_high:
            base_rec = "LONG"
            base_conf = 0.6
        elif current_price < va_low:
            base_rec = "SHORT"
            base_conf = 0.6
        elif current_price > poc:
            base_rec = "LONG"
            base_conf = 0.55
        else:
            base_rec = "SHORT"
            base_conf = 0.55
        
        # Adjust based on profile shape
        shape = profile["profile_shape"]
        if shape == "d":
            base_conf += 0.05  # Balanced profile increases confidence
        elif shape == "thin":
            base_conf -= 0.1  # Thin profile decreases confidence
        
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
        
        return base_rec, min(base_conf, 0.9)

    def _profile_to_dict(self, profile: Dict) -> Dict:
        """Convert profile to dictionary."""
        return {
            "poc": profile["poc"],
            "value_area_high": profile["value_area_high"],
            "value_area_low": profile["value_area_low"],
            "value_area_volume_pct": profile["value_area_volume_pct"],
            "total_volume": profile["total_volume"],
            "profile_shape": profile["profile_shape"],
            "nodes": [
                {
                    "price_level": n.price_level,
                    "volume": n.volume,
                    "relative_volume": n.relative_volume,
                    "type": n.type,
                }
                for n in profile["nodes"]
            ],
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
async def run_volume_profile_analysis(
    ticker: str,
    timeframe: str = "5m",
    include_mirofish: bool = True,
) -> dict:
    """Run volume profile analysis directly."""
    agent = VolumeProfileAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"vp-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="volume_profile",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
