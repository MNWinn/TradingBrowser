"""
Regime Detection Agent with MiroFish Regime Alignment

This agent detects market regimes and aligns them with MiroFish
predictions for enhanced regime classification.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any, Optional, Dict

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot
from app.services.agents.fleet.mirofish_assessment import run_mirofish_assessment
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class RegimeDetectionAgent(BaseAgent):
    """
    Market regime detection with MiroFish alignment.
    
    Specialization:
    - Trending vs mean-reverting regime detection
    - Volatility regime classification
    - MiroFish regime alignment validation
    - Multi-factor regime scoring
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "regime_detection",
            agent_type="regime_detection",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "regime_detection_with_mirofish"
        self.has_mirofish_integration = True

    async def _run(self, payload: dict) -> dict:
        """
        Execute regime detection with MiroFish alignment.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframe', 'lookback'
            
        Returns:
            Dict with regime classification and MiroFish alignment
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")
        
        timeframe = payload.get("timeframe", "5m")
        lookback = payload.get("lookback", 100)
        include_mirofish = payload.get("include_mirofish", True)
        
        self.log(f"Starting regime detection for {ticker} on {timeframe}", "info")
        
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
                "regime": "unknown",
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
            }
        
        # Prepare data
        df = self._prepare_data(bars)
        
        # Calculate regime metrics
        metrics = self._calculate_regime_metrics(df)
        
        # Classify regime
        regime, regime_conf = self._classify_regime(metrics)
        
        # Get MiroFish alignment
        mirofish_data = None
        mirofish_alignment = None
        
        if include_mirofish:
            try:
                mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
                mirofish_alignment = self._calculate_mirofish_alignment(regime, metrics, mirofish_data)
            except Exception as e:
                self.log(f"MiroFish alignment failed: {e}", "warning")
        
        # Generate recommendation
        recommendation, confidence = self._generate_recommendation(regime, metrics, mirofish_alignment)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "timeframe": timeframe,
            "has_mirofish_integration": True,
            "mirofish_data": mirofish_data,
            "regime": regime,
            "regime_confidence": regime_conf,
            "metrics": metrics,
            "mirofish_alignment": mirofish_alignment,
            "recommendation": recommendation,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Regime detection complete for {ticker}: {regime} (confidence: {confidence:.2f})", "info")
        
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

    def _calculate_regime_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate regime detection metrics."""
        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        # Trend metrics
        returns = close.pct_change().dropna()
        
        # ADX calculation
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
        
        atr = tr.rolling(window=14).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=14).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=14).mean() / atr
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()
        
        # Volatility
        volatility = returns.rolling(window=20).std() * np.sqrt(252)
        
        # Price change
        price_change_5d = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
        price_change_20d = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100 if len(close) >= 20 else 0
        
        # Trend strength (linear regression slope)
        x = np.arange(len(close))
        slope = np.polyfit(x, close, 1)[0]
        
        # Mean reversion score (autocorrelation)
        autocorr = returns.autocorr(lag=1) if len(returns) > 1 else 0
        
        return {
            "adx": round(adx.iloc[-1], 2) if not pd.isna(adx.iloc[-1]) else 20,
            "plus_di": round(plus_di.iloc[-1], 2) if not pd.isna(plus_di.iloc[-1]) else 20,
            "minus_di": round(minus_di.iloc[-1], 2) if not pd.isna(minus_di.iloc[-1]) else 20,
            "volatility_annualized": round(volatility.iloc[-1] * 100, 2) if not pd.isna(volatility.iloc[-1]) else 20,
            "price_change_5d_pct": round(price_change_5d, 2),
            "price_change_20d_pct": round(price_change_20d, 2),
            "trend_slope": round(slope, 4),
            "autocorrelation": round(autocorr, 3),
            "current_price": round(close.iloc[-1], 2),
        }

    def _classify_regime(self, metrics: Dict) -> tuple:
        """Classify market regime based on metrics."""
        adx = metrics.get("adx", 20)
        volatility = metrics.get("volatility_annualized", 20)
        trend_slope = metrics.get("trend_slope", 0)
        autocorr = metrics.get("autocorrelation", 0)
        
        # Trend strength
        if adx > 25:
            if trend_slope > 0:
                regime = "trending_up"
            else:
                regime = "trending_down"
            confidence = min(0.9, 0.5 + (adx - 25) / 50)
        
        # Volatility regime
        elif volatility > 40:
            regime = "volatile"
            confidence = min(0.85, volatility / 100)
        
        # Mean reversion
        elif abs(autocorr) > 0.3 and adx < 20:
            regime = "mean_reverting"
            confidence = min(0.8, abs(autocorr))
        
        # Calm/range-bound
        else:
            regime = "calm"
            confidence = 0.6
        
        return regime, round(confidence, 2)

    def _calculate_mirofish_alignment(self, regime: str, metrics: Dict, mirofish_data: Dict) -> Dict:
        """Calculate alignment between technical regime and MiroFish prediction."""
        bias = mirofish_data.get("directional_bias", "NEUTRAL")
        miro_conf = mirofish_data.get("confidence", 0.5)
        
        # Determine if regime aligns with MiroFish
        alignment_score = 0.5
        alignment_status = "neutral"
        
        if regime == "trending_up":
            if bias == "BULLISH":
                alignment_score = 0.8 + miro_conf * 0.2
                alignment_status = "strongly_aligned"
            elif bias == "BEARISH":
                alignment_score = 0.2
                alignment_status = "contradiction"
            else:
                alignment_score = 0.5 + miro_conf * 0.1
                alignment_status = "weakly_aligned"
        
        elif regime == "trending_down":
            if bias == "BEARISH":
                alignment_score = 0.8 + miro_conf * 0.2
                alignment_status = "strongly_aligned"
            elif bias == "BULLISH":
                alignment_score = 0.2
                alignment_status = "contradiction"
            else:
                alignment_score = 0.5 + miro_conf * 0.1
                alignment_status = "weakly_aligned"
        
        elif regime == "mean_reverting":
            if bias == "NEUTRAL":
                alignment_score = 0.9
                alignment_status = "strongly_aligned"
            else:
                alignment_score = 0.6
                alignment_status = "moderate"
        
        elif regime == "volatile":
            alignment_score = 0.5
            alignment_status = "caution"
        
        else:  # calm
            if bias == "NEUTRAL":
                alignment_score = 0.8
                alignment_status = "aligned"
            else:
                alignment_score = 0.6
                alignment_status = "potential_breakout"
        
        return {
            "alignment_score": round(alignment_score, 2),
            "alignment_status": alignment_status,
            "mirofish_bias": bias,
            "mirofish_confidence": miro_conf,
            "regime": regime,
        }

    def _generate_recommendation(self, regime: str, metrics: Dict, mirofish_alignment: Optional[Dict]) -> tuple:
        """Generate trading recommendation based on regime and MiroFish alignment."""
        
        # Base recommendation from regime
        regime_recommendations = {
            "trending_up": ("LONG", 0.7),
            "trending_down": ("SHORT", 0.7),
            "mean_reverting": ("MEAN_REVERSION", 0.6),
            "volatile": ("NO_TRADE", 0.4),
            "calm": ("NEUTRAL", 0.5),
        }
        
        base_rec, base_conf = regime_recommendations.get(regime, ("NEUTRAL", 0.5))
        
        # Adjust based on MiroFish alignment
        if mirofish_alignment:
            alignment_score = mirofish_alignment.get("alignment_score", 0.5)
            alignment_status = mirofish_alignment.get("alignment_status", "neutral")
            
            if alignment_status == "strongly_aligned":
                return base_rec, min(0.95, base_conf * 0.7 + alignment_score * 0.3)
            elif alignment_status == "contradiction":
                return "NO_TRADE", 0.4
            elif alignment_status == "caution":
                return "NO_TRADE", 0.5
            else:
                return base_rec, min(0.9, base_conf * 0.6 + alignment_score * 0.4)
        
        return base_rec, base_conf

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
async def run_regime_detection(
    ticker: str,
    timeframe: str = "5m",
    include_mirofish: bool = True,
) -> dict:
    """Run regime detection directly."""
    agent = RegimeDetectionAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"regime-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="regime_detection",
        payload={
            "ticker": ticker,
            "timeframe": timeframe,
            "include_mirofish": include_mirofish,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
