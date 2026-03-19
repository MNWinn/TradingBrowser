"""
Market Scanner Agent with MiroFish Signals Integration

This agent scans the market for opportunities and incorporates
MiroFish predictive signals for enhanced scanning accuracy.
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


class MarketScannerAgent(BaseAgent):
    """
    Market scanner with MiroFish signal integration.
    
    Specialization:
    - Multi-ticker screening with MiroFish filtering
    - Volume spike detection with MiroFish confirmation
    - Opportunity ranking with predictive bias
    - Real-time market scanning
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "market_scanner",
            agent_type="market_scanner",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "market_scanning_with_mirofish"
        self.has_mirofish_integration = True
        self.default_tickers = [
            "SPY", "QQQ", "IWM", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "NVDA", "META", "AMD", "NFLX", "CRM", "BABA", "UBER", "COIN",
            "PLTR", "ROKU", "SQ", "PYPL", "SHOP", "ZM", "DOCU", "PTON"
        ]

    async def _run(self, payload: dict) -> dict:
        """
        Execute market scan with MiroFish integration.
        
        Args:
            payload: Optional 'tickers' list, 'include_mirofish', 'max_results'
            
        Returns:
            Dict with scanned opportunities and MiroFish-enhanced rankings
        """
        tickers = payload.get("tickers", self.default_tickers)
        include_mirofish = payload.get("include_mirofish", True)
        max_results = payload.get("max_results", 10)
        
        self.log(f"Starting market scan for {len(tickers)} tickers", "info")
        
        # Scan all tickers
        scan_tasks = [self._scan_ticker(t, include_mirofish) for t in tickers]
        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        
        # Filter valid results
        valid_results = [
            r for r in results 
            if isinstance(r, dict) and r.get("eligible", False)
        ]
        
        # Sort by composite score (includes MiroFish if available)
        valid_results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        
        # Get top opportunities
        top_opportunities = valid_results[:max_results]
        
        # Calculate market-wide statistics
        market_stats = self._calculate_market_stats(valid_results)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(top_opportunities)
        
        # Calculate confidence
        confidence = self._calculate_confidence(valid_results, len(tickers))
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "has_mirofish_integration": True,
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            "tickers_scanned": len(tickers),
            "eligible_tickers": len(valid_results),
            "market_stats": market_stats,
            "top_opportunities": top_opportunities,
            "recommendation": recommendation,
            "confidence": confidence,
        }
        
        self.log(f"Market scan complete. Found {len(valid_results)} eligible tickers", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    async def _scan_ticker(self, ticker: str, include_mirofish: bool) -> dict:
        """Scan a single ticker with optional MiroFish integration."""
        try:
            # Get quote and basic data
            quote = get_quote_snapshot(ticker)
            bars_data = get_bars_snapshot(ticker, timeframe="5m", limit=50)
            bars = bars_data.get("bars", [])
            
            if len(bars) < 20:
                return {"ticker": ticker, "eligible": False, "reason": "insufficient_data"}
            
            # Basic metrics
            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"])
            df = df.sort_values("t").reset_index(drop=True)
            df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
            
            current_price = df["close"].iloc[-1]
            current_volume = df["volume"].iloc[-1]
            avg_volume_20 = df["volume"].tail(20).mean()
            
            # Price changes
            price_change_1d = ((df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20]) * 100
            
            # Volume spike
            volume_spike = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
            
            # Get MiroFish prediction if enabled
            mirofish_data = None
            mirofish_score = 0.5  # Neutral baseline
            
            if include_mirofish:
                try:
                    mirofish_data = await run_mirofish_assessment(ticker, deep_mode=False)
                    bias = mirofish_data.get("directional_bias", "NEUTRAL")
                    conf = mirofish_data.get("confidence", 0.5)
                    
                    # Convert bias to score
                    if bias == "BULLISH":
                        mirofish_score = 0.5 + (conf * 0.5)
                    elif bias == "BEARISH":
                        mirofish_score = 0.5 - (conf * 0.5)
                except Exception:
                    pass
            
            # Calculate composite score (0-100)
            # Include MiroFish bias in scoring
            base_score = self._calculate_base_score(volume_spike, abs(price_change_1d))
            composite_score = base_score * (0.7 + mirofish_score * 0.3)
            
            return {
                "ticker": ticker,
                "eligible": True,
                "composite_score": round(composite_score, 2),
                "base_score": round(base_score, 2),
                "mirofish_score": round(mirofish_score, 2),
                "mirofish_data": mirofish_data,
                "price": round(current_price, 2),
                "volume_spike": round(volume_spike, 2),
                "price_change_1d_pct": round(price_change_1d, 2),
            }
            
        except Exception as e:
            return {"ticker": ticker, "eligible": False, "reason": f"error: {str(e)}"}

    def _calculate_base_score(self, volume_spike: float, price_change: float) -> float:
        """Calculate base opportunity score."""
        volume_score = min((volume_spike - 1) * 15, 30) if volume_spike > 1 else 0
        move_score = min(price_change * 3, 30)
        return volume_score + move_score + 40  # Base of 40

    def _calculate_market_stats(self, results: list) -> dict:
        """Calculate market-wide statistics."""
        if not results:
            return {"status": "no_data"}
        
        scores = [r.get("composite_score", 0) for r in results]
        mirofish_scores = [r.get("mirofish_score", 0.5) for r in results if r.get("mirofish_data")]
        
        bullish_count = sum(1 for r in results if r.get("mirofish_score", 0.5) > 0.6)
        bearish_count = sum(1 for r in results if r.get("mirofish_score", 0.5) < 0.4)
        
        return {
            "avg_composite_score": round(np.mean(scores), 2),
            "max_composite_score": round(max(scores), 2),
            "avg_mirofish_score": round(np.mean(mirofish_scores), 2) if mirofish_scores else None,
            "sentiment": "bullish" if bullish_count > bearish_count else "bearish",
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
        }

    def _calculate_confidence(self, valid_results: list, total_scanned: int) -> float:
        """Calculate confidence score for the scan."""
        if total_scanned == 0:
            return 0.0
        
        coverage = len(valid_results) / total_scanned
        mirofish_coverage = sum(1 for r in valid_results if r.get("mirofish_data")) / len(valid_results) if valid_results else 0
        
        confidence = (coverage * 0.5 + mirofish_coverage * 0.5)
        return round(min(confidence, 0.95), 3)

    def _determine_recommendation(self, top_opportunities: list) -> str:
        """Determine overall recommendation from scan results."""
        if not top_opportunities:
            return "NO_TRADE"
        
        avg_score = np.mean([o.get("composite_score", 0) for o in top_opportunities[:3]])
        
        if avg_score >= 65:
            return "SCAN_ACTIVE"
        elif avg_score >= 45:
            return "SCAN_SELECTIVE"
        else:
            return "SCAN_IDLE"

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
async def run_market_scan_with_mirofish(
    tickers: Optional[list] = None,
    max_results: int = 10,
) -> dict:
    """Run market scan with MiroFish directly."""
    agent = MarketScannerAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"scanner-mirofish-{datetime.now(timezone.utc).timestamp()}",
        agent_type="market_scanner",
        payload={
            "tickers": tickers,
            "include_mirofish": True,
            "max_results": max_results,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
