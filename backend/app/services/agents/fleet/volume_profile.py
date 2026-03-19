"""
Volume Profile Agent - Analyzes volume at price levels.

This agent creates volume profile analysis to identify value areas,
point of control (POC), and high/low volume nodes for trading decisions.
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
class VolumeNode:
    """Represents a volume concentration at a price level."""
    price_level: float
    volume: float
    relative_volume: float  # vs average
    bar_count: int
    type: str  # "poc", "value_area", "low_volume", "single_print"


@dataclass
class VolumeProfile:
    """Complete volume profile for a timeframe."""
    poc_price: float  # Point of Control (highest volume)
    value_area_high: float
    value_area_low: float
    value_area_volume_pct: float
    total_volume: float
    nodes: List[VolumeNode]
    profile_shape: str  # "d", "p", "b", "thin"


class VolumeProfileAgent(BaseAgent):
    """
    Volume profile analysis specialist.
    
    Specialization:
    - Volume Profile (fixed range and session-based)
    - Point of Control (POC) identification
    - Value Area (VA) calculation (70% of volume)
    - Volume delta analysis
    - Footprint analysis proxy
    - Profile shape classification
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
        self.specialization = "volume_profile_analysis"
        self.value_area_pct = 0.70  # 70% of volume
        self.min_bars = 30

    async def _run(self, payload: dict) -> dict:
        """
        Execute volume profile analysis.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback', 'num_rows'
            
        Returns:
            Dict with volume profile analysis and trading implications
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        num_rows = payload.get("num_rows", 24)  # Number of price rows for profile
        
        self.log(f"Starting volume profile analysis for {ticker} on {timeframe}", "info")
        
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
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Build volume profile
        profile = self._build_volume_profile(df, num_rows)
        
        # Calculate volume metrics
        volume_metrics = self._calculate_volume_metrics(df, profile)
        
        # Analyze price position relative to profile
        position_analysis = self._analyze_position(df, profile)
        
        # Detect volume anomalies
        anomalies = self._detect_anomalies(df, profile)
        
        # Calculate confidence
        confidence_data = self._calculate_confidence(profile, df)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(position_analysis, volume_metrics, profile)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "current_price": round(df["close"].iloc[-1], 2),
            "volume_profile": {
                "poc_price": round(profile.poc_price, 2),
                "value_area_high": round(profile.value_area_high, 2),
                "value_area_low": round(profile.value_area_low, 2),
                "value_area_range": round(profile.value_area_high - profile.value_area_low, 2),
                "value_area_volume_pct": round(profile.value_area_volume_pct * 100, 1),
                "total_volume": int(profile.total_volume),
                "profile_shape": profile.profile_shape,
            },
            "nodes": [
                {
                    "price": round(n.price_level, 2),
                    "volume": int(n.volume),
                    "relative_volume": round(n.relative_volume, 2),
                    "bar_count": n.bar_count,
                    "type": n.type,
                }
                for n in profile.nodes[:15]  # Top 15 nodes
            ],
            "position_analysis": position_analysis,
            "volume_metrics": volume_metrics,
            "anomalies": anomalies,
            "recommendation": recommendation,
            "confidence": confidence_data["overall_confidence"],
            "confidence_breakdown": confidence_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Volume profile analysis complete for {ticker}: POC at {profile.poc_price:.2f}", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    def _prepare_data(self, bars: list) -> pd.DataFrame:
        """Prepare price and volume data."""
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        
        # Calculate typical price for each bar
        df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
        
        # Calculate volume delta (proxy using close position in range)
        df["close_position"] = (df["close"] - df["low"]) / (df["high"] - df["low"])
        df["volume_delta"] = df["volume"] * (2 * df["close_position"] - 1)  # -vol to +vol
        
        return df

    def _build_volume_profile(self, df: pd.DataFrame, num_rows: int) -> VolumeProfile:
        """Build volume profile from price/volume data."""
        price_min = df["low"].min()
        price_max = df["high"].max()
        price_range = price_max - price_min
        
        if price_range == 0:
            price_range = price_min * 0.01  # 1% fallback
        
        row_size = price_range / num_rows
        
        # Initialize volume rows
        rows = []
        for i in range(num_rows):
            price_level = price_min + (i * row_size) + (row_size / 2)
            rows.append({
                "price": price_level,
                "volume": 0,
                "bar_count": 0,
                "buys": 0,  # Proxy based on close position
                "sells": 0,
            })
        
        # Distribute volume into rows
        for _, bar in df.iterrows():
            bar_range = bar["high"] - bar["low"]
            if bar_range == 0:
                bar_range = bar["close"] * 0.001
            
            # Distribute volume across price range of bar
            for row in rows:
                if bar["low"] <= row["price"] <= bar["high"]:
                    # Weight by how much of bar range this row represents
                    overlap = min(bar["high"], row["price"] + row_size/2) - max(bar["low"], row["price"] - row_size/2)
                    volume_contribution = bar["volume"] * (overlap / bar_range)
                    
                    row["volume"] += volume_contribution
                    row["bar_count"] += 1
                    
                    # Proxy for buy/sell volume
                    if bar["close"] > bar["open"]:
                        row["buys"] += volume_contribution * 0.6
                        row["sells"] += volume_contribution * 0.4
                    else:
                        row["buys"] += volume_contribution * 0.4
                        row["sells"] += volume_contribution * 0.6
        
        # Convert to DataFrame for easier manipulation
        profile_df = pd.DataFrame(rows)
        profile_df = profile_df[profile_df["volume"] > 0]  # Remove empty rows
        
        if len(profile_df) == 0:
            # Fallback if no volume distributed
            return VolumeProfile(
                poc_price=df["close"].iloc[-1],
                value_area_high=df["high"].max(),
                value_area_low=df["low"].min(),
                value_area_volume_pct=1.0,
                total_volume=df["volume"].sum(),
                nodes=[],
                profile_shape="thin"
            )
        
        # Find POC (Point of Control)
        poc_idx = profile_df["volume"].idxmax()
        poc_price = profile_df.loc[poc_idx, "price"]
        
        # Calculate Value Area (70% of volume around POC)
        total_volume = profile_df["volume"].sum()
        target_volume = total_volume * self.value_area_pct
        
        # Start from POC and expand
        poc_position = profile_df.index.get_loc(poc_idx)
        va_low_idx = poc_position
        va_high_idx = poc_position
        current_volume = profile_df.loc[poc_idx, "volume"]
        
        while current_volume < target_volume and (va_low_idx > 0 or va_high_idx < len(profile_df) - 1):
            # Add next row with highest volume
            low_volume = profile_df.iloc[va_low_idx - 1]["volume"] if va_low_idx > 0 else 0
            high_volume = profile_df.iloc[va_high_idx + 1]["volume"] if va_high_idx < len(profile_df) - 1 else 0
            
            if low_volume >= high_volume and va_low_idx > 0:
                va_low_idx -= 1
                current_volume += low_volume
            elif va_high_idx < len(profile_df) - 1:
                va_high_idx += 1
                current_volume += high_volume
            else:
                break
        
        value_area_low = profile_df.iloc[va_low_idx]["price"]
        value_area_high = profile_df.iloc[va_high_idx]["price"]
        
        # Create volume nodes
        avg_volume = profile_df["volume"].mean()
        nodes = []
        
        for _, row in profile_df.iterrows():
            relative_vol = row["volume"] / avg_volume if avg_volume > 0 else 1
            
            # Determine node type
            if row["price"] == poc_price:
                node_type = "poc"
            elif value_area_low <= row["price"] <= value_area_high:
                node_type = "value_area"
            elif relative_vol < 0.5:
                node_type = "low_volume"
            else:
                node_type = "single_print"
            
            nodes.append(VolumeNode(
                price_level=row["price"],
                volume=row["volume"],
                relative_volume=relative_vol,
                bar_count=row["bar_count"],
                type=node_type
            ))
        
        # Sort by volume (descending)
        nodes.sort(key=lambda n: n.volume, reverse=True)
        
        # Classify profile shape
        profile_shape = self._classify_profile_shape(profile_df, poc_price, value_area_low, value_area_high)
        
        return VolumeProfile(
            poc_price=poc_price,
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            value_area_volume_pct=current_volume / total_volume,
            total_volume=total_volume,
            nodes=nodes,
            profile_shape=profile_shape
        )

    def _classify_profile_shape(
        self,
        profile_df: pd.DataFrame,
        poc_price: float,
        va_low: float,
        va_high: float
    ) -> str:
        """Classify the shape of the volume profile."""
        if len(profile_df) < 5:
            return "thin"
        
        # Normalize volumes
        volumes = profile_df["volume"].values
        volumes_norm = volumes / volumes.max()
        
        # Find POC position
        poc_idx = (profile_df["price"] - poc_price).abs().idxmin()
        poc_position = profile_df.index.get_loc(poc_idx) / len(profile_df)
        
        # Calculate skewness
        mean_price = np.average(profile_df["price"], weights=profile_df["volume"])
        
        # D-shaped: POC near one end, long tail
        if poc_position < 0.3 or poc_position > 0.7:
            return "d"
        
        # P-shaped: POC in upper half
        if poc_position > 0.6:
            return "p"
        
        # b-shaped: POC in lower half
        if poc_position < 0.4:
            return "b"
        
        # Thin/balanced: POC in middle, relatively even distribution
        return "balanced"

    def _calculate_volume_metrics(self, df: pd.DataFrame, profile: VolumeProfile) -> dict:
        """Calculate additional volume metrics."""
        current_price = df["close"].iloc[-1]
        
        # Volume trend
        recent_volume = df["volume"].tail(10).mean()
        older_volume = df["volume"].tail(30).head(20).mean()
        volume_trend = "increasing" if recent_volume > older_volume * 1.1 else (
            "decreasing" if recent_volume < older_volume * 0.9 else "stable"
        )
        
        # Volume delta (buying vs selling pressure)
        total_delta = df["volume_delta"].sum()
        cumulative_delta = df["volume_delta"].cumsum().iloc[-1]
        
        # Delta as percentage of total volume
        delta_pct = (abs(total_delta) / df["volume"].sum()) * 100
        
        # VWAP
        vwap = (df["typical_price"] * df["volume"]).sum() / df["volume"].sum()
        
        # Price vs VWAP
        price_vs_vwap = ((current_price - vwap) / vwap) * 100
        
        return {
            "total_volume": int(df["volume"].sum()),
            "avg_volume_20": int(df["volume"].tail(20).mean()),
            "volume_trend": volume_trend,
            "volume_delta": int(total_delta),
            "cumulative_delta": int(cumulative_delta),
            "delta_bias": "buying" if total_delta > 0 else "selling",
            "delta_strength_pct": round(delta_pct, 2),
            "vwap": round(vwap, 2),
            "price_vs_vwap_pct": round(price_vs_vwap, 2),
        }

    def _analyze_position(self, df: pd.DataFrame, profile: VolumeProfile) -> dict:
        """Analyze current price position relative to volume profile."""
        current_price = df["close"].iloc[-1]
        
        # Position relative to value area
        if current_price > profile.value_area_high:
            position = "above_va"
            distance_from_poc = current_price - profile.poc_price
        elif current_price < profile.value_area_low:
            position = "below_va"
            distance_from_poc = profile.poc_price - current_price
        else:
            position = "inside_va"
            distance_from_poc = abs(current_price - profile.poc_price)
        
        # Distance percentages
        va_range = profile.value_area_high - profile.value_area_low
        
        if va_range > 0:
            if current_price > profile.value_area_high:
                distance_pct = ((current_price - profile.value_area_high) / va_range) * 100
            elif current_price < profile.value_area_low:
                distance_pct = ((profile.value_area_low - current_price) / va_range) * 100
            else:
                # Inside VA - show position within VA
                va_position = (current_price - profile.value_area_low) / va_range
                distance_pct = (va_position - 0.5) * 100  # -50% to +50%
        else:
            distance_pct = 0
        
        # Find nearest high volume node
        high_vol_nodes = [n for n in profile.nodes if n.relative_volume > 1.5]
        
        nearest_node = None
        nearest_distance = float('inf')
        for node in high_vol_nodes:
            dist = abs(node.price_level - current_price)
            if dist < nearest_distance:
                nearest_distance = dist
                nearest_node = node
        
        return {
            "position": position,
            "distance_from_poc": round(distance_from_poc, 2),
            "distance_from_poc_pct": round((distance_from_poc / profile.poc_price) * 100, 2),
            "distance_from_va_pct": round(distance_pct, 2),
            "nearest_high_volume_node": {
                "price": round(nearest_node.price_level, 2) if nearest_node else None,
                "distance": round(nearest_distance, 2) if nearest_node else None,
                "volume_ratio": round(nearest_node.relative_volume, 2) if nearest_node else None,
            },
        }

    def _detect_anomalies(self, df: pd.DataFrame, profile: VolumeProfile) -> List[dict]:
        """Detect volume-based anomalies."""
        anomalies = []
        
        # Volume spike detection
        avg_volume = df["volume"].mean()
        std_volume = df["volume"].std()
        
        recent_bars = df.tail(5)
        for idx, bar in recent_bars.iterrows():
            if bar["volume"] > avg_volume + (3 * std_volume):
                anomalies.append({
                    "type": "volume_spike",
                    "timestamp": idx,
                    "volume": int(bar["volume"]),
                    "spike_ratio": round(bar["volume"] / avg_volume, 2),
                    "description": f"Volume spike: {bar['volume']/avg_volume:.1f}x average"
                })
        
        # Single print detection (low volume at edges)
        for node in profile.nodes:
            if node.type == "single_print" and node.relative_volume < 0.3:
                anomalies.append({
                    "type": "single_print",
                    "price": round(node.price_level, 2),
                    "description": f"Single print node at {node.price_level:.2f} (low volume)"
                })
        
        return anomalies[:5]  # Top 5 anomalies

    def _calculate_confidence(self, profile: VolumeProfile, df: pd.DataFrame) -> dict:
        """Calculate overall confidence."""
        # Data quality
        data_quality = min(len(df) / 100, 1.0)
        
        # Profile quality
        if profile.total_volume > 0:
            va_quality = profile.value_area_volume_pct
        else:
            va_quality = 0.5
        
        # Node quality
        if profile.nodes:
            avg_node_volume = np.mean([n.relative_volume for n in profile.nodes])
            node_quality = min(avg_node_volume, 1.0)
        else:
            node_quality = 0.5
        
        overall = (data_quality * 0.3 + va_quality * 0.4 + node_quality * 0.3)
        
        return {
            "overall_confidence": round(min(overall, 0.95), 3),
            "data_quality": round(data_quality, 3),
            "va_quality": round(va_quality, 3),
            "node_quality": round(node_quality, 3),
        }

    def _determine_recommendation(
        self,
        position_analysis: dict,
        volume_metrics: dict,
        profile: VolumeProfile
    ) -> str:
        """Determine trading recommendation based on volume profile."""
        position = position_analysis.get("position")
        delta_bias = volume_metrics.get("delta_bias")
        profile_shape = profile.profile_shape
        
        # Above value area
        if position == "above_va":
            if delta_bias == "buying":
                return "LONG"  # Breakout with volume
            else:
                return "WATCHLIST_SHORT"  # Potential rejection
        
        # Below value area
        if position == "below_va":
            if delta_bias == "selling":
                return "SHORT"  # Breakdown with volume
            else:
                return "WATCHLIST_LONG"  # Potential bounce
        
        # Inside value area
        if position == "inside_va":
            distance_from_poc_pct = position_analysis.get("distance_from_poc_pct", 0)
            
            if abs(distance_from_poc_pct) < 1:  # Near POC
                return "WATCHLIST"  # Balanced, wait for direction
            elif distance_from_poc_pct > 0:  # Upper half of VA
                if delta_bias == "buying":
                    return "WATCHLIST_LONG"
                else:
                    return "WATCHLIST_SHORT"
            else:  # Lower half of VA
                if delta_bias == "selling":
                    return "WATCHLIST_SHORT"
                else:
                    return "WATCHLIST_LONG"
        
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
async def run_volume_profile_analysis(
    ticker: str,
    timeframe: str = "5m",
    lookback: int = 100,
    num_rows: int = 24,
) -> dict:
    """Run volume profile analysis directly."""
    agent = VolumeProfileAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"vp-direct-{ticker}-{datetime.now(timezone.utc).timestamp()}",
        agent_type="volume_profile",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "lookback": lookback,
            "num_rows": num_rows,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
