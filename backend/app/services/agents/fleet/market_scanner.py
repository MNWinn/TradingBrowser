"""
Market Scanner Agent - Scans entire market for trading opportunities.

This agent scans multiple tickers simultaneously to identify the best
opportunities based on volume, volatility, and technical criteria.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.market_data import get_bars_snapshot, get_quote_snapshot
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class MarketScannerAgent(BaseAgent):
    """
    Market-wide opportunity scanner.
    
    Specialization:
    - Multi-ticker screening and ranking
    - Volume spike detection
    - Volatility regime identification
    - Relative strength analysis
    - Gap detection
    - Unusual options activity proxy (via volume)
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
        self.specialization = "market_wide_scanning"
        self.default_tickers = [
            "SPY", "QQQ", "IWM", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
            "NVDA", "META", "AMD", "NFLX", "CRM", "BABA", "UBER", "COIN",
            "PLTR", "ROKU", "SQ", "PYPL", "SHOP", "ZM", "DOCU", "PTON"
        ]
        self.scan_criteria = {
            "min_volume": 100000,
            "min_price": 5.0,
            "max_price": 5000.0,
        }

    async def _run(self, payload: dict) -> dict:
        """
        Execute market scan.
        
        Args:
            payload: Optional 'tickers' list, 'criteria' dict, 'max_results' int
            
        Returns:
            Dict with ranked opportunities and scan metadata
        """
        tickers = payload.get("tickers", self.default_tickers)
        criteria = {**self.scan_criteria, **payload.get("criteria", {})}
        max_results = payload.get("max_results", 10)
        
        self.log(f"Starting market scan for {len(tickers)} tickers", "info")
        
        # Scan all tickers concurrently
        scan_tasks = [self._scan_ticker(t, criteria) for t in tickers]
        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        
        # Filter out errors and sort by opportunity score
        valid_results = [
            r for r in results 
            if isinstance(r, dict) and r.get("eligible", False)
        ]
        
        # Sort by composite score
        valid_results.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
        
        # Calculate market-wide statistics
        market_stats = self._calculate_market_stats(valid_results)
        
        # Determine top opportunities
        top_opportunities = valid_results[:max_results]
        
        # Calculate confidence based on data quality
        confidence = self._calculate_scan_confidence(valid_results, len(tickers))
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "scan_timestamp": datetime.now(timezone.utc).isoformat(),
            "tickers_scanned": len(tickers),
            "eligible_tickers": len(valid_results),
            "market_stats": market_stats,
            "top_opportunities": top_opportunities,
            "all_results": valid_results if payload.get("include_all") else None,
            "recommendation": self._determine_recommendation(top_opportunities),
            "confidence": confidence,
        }
        
        self.log(f"Market scan complete. Found {len(valid_results)} eligible tickers", "info")
        
        # Store results
        await self._store_results(output)
        
        return output

    async def _scan_ticker(self, ticker: str, criteria: dict) -> dict:
        """Scan a single ticker for opportunities."""
        try:
            # Get quote and bars
            quote = get_quote_snapshot(ticker)
            bars_data = get_bars_snapshot(ticker, timeframe="5m", limit=50)
            bars = bars_data.get("bars", [])
            
            if not bars or len(bars) < 20:
                return {"ticker": ticker, "eligible": False, "reason": "insufficient_data"}
            
            # Create DataFrame
            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"])
            df = df.sort_values("t").reset_index(drop=True)
            df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
            
            # Calculate metrics
            current_price = df["close"].iloc[-1]
            current_volume = df["volume"].iloc[-1]
            avg_volume_20 = df["volume"].tail(20).mean()
            
            # Check criteria
            if current_price < criteria["min_price"] or current_price > criteria["max_price"]:
                return {"ticker": ticker, "eligible": False, "reason": "price_out_of_range"}
            
            if avg_volume_20 < criteria["min_volume"]:
                return {"ticker": ticker, "eligible": False, "reason": "low_volume"}
            
            # Calculate opportunity metrics
            volume_spike = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1.0
            
            # Price change metrics
            price_change_1d = ((df["close"].iloc[-1] - df["close"].iloc[-20]) / df["close"].iloc[-20]) * 100
            price_change_1h = ((df["close"].iloc[-1] - df["close"].iloc[-12]) / df["close"].iloc[-12]) * 100 if len(df) >= 12 else 0
            
            # Volatility (ATR-based)
            high_low = df["high"] - df["low"]
            high_close = np.abs(df["high"] - df["close"].shift())
            low_close = np.abs(df["low"] - df["close"].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = np.max(ranges, axis=1)
            atr = true_range.rolling(14).mean().iloc[-1]
            volatility_pct = (atr / current_price) * 100
            
            # Trend strength (simple slope)
            price_slope = np.polyfit(range(len(df.tail(20))), df["close"].tail(20), 1)[0]
            
            # Gap detection
            prev_close = df["close"].iloc[-2] if len(df) > 1 else df["close"].iloc[-1]
            gap_pct = ((df["open"].iloc[-1] - prev_close) / prev_close) * 100
            
            # Composite opportunity score (0-100)
            opportunity_score = self._calculate_opportunity_score(
                volume_spike=volume_spike,
                volatility_pct=volatility_pct,
                price_change_1d=abs(price_change_1d),
                price_slope=abs(price_slope),
                gap_pct=abs(gap_pct),
            )
            
            return {
                "ticker": ticker,
                "eligible": True,
                "opportunity_score": round(opportunity_score, 2),
                "price": round(current_price, 2),
                "volume_spike": round(volume_spike, 2),
                "avg_volume_20d": int(avg_volume_20),
                "price_change_1d_pct": round(price_change_1d, 2),
                "price_change_1h_pct": round(price_change_1h, 2),
                "volatility_pct": round(volatility_pct, 2),
                "trend_slope": round(price_slope, 4),
                "gap_pct": round(gap_pct, 2),
                "data_source": bars_data.get("source", "unknown"),
                "simulated": bars_data.get("simulated", False),
            }
            
        except Exception as e:
            return {"ticker": ticker, "eligible": False, "reason": f"error: {str(e)}"}

    def _calculate_opportunity_score(
        self,
        volume_spike: float,
        volatility_pct: float,
        price_change_1d: float,
        price_slope: float,
        gap_pct: float,
    ) -> float:
        """Calculate composite opportunity score (0-100)."""
        # Volume component (0-25 points)
        volume_score = min((volume_spike - 1) * 10, 25) if volume_spike > 1 else 0
        
        # Volatility component (0-25 points)
        vol_score = min(volatility_pct * 5, 25)
        
        # Price movement component (0-25 points)
        move_score = min(price_change_1d * 2, 25)
        
        # Momentum component (0-25 points)
        momentum_score = min(abs(price_slope) * 100, 25)
        
        # Gap bonus (0-10 bonus points)
        gap_score = min(abs(gap_pct) * 2, 10)
        
        return volume_score + vol_score + move_score + momentum_score + gap_score

    def _calculate_market_stats(self, results: list) -> dict:
        """Calculate market-wide statistics from scan results."""
        if not results:
            return {"status": "no_data"}
        
        scores = [r.get("opportunity_score", 0) for r in results]
        volume_spikes = [r.get("volume_spike", 1) for r in results]
        price_changes = [r.get("price_change_1d_pct", 0) for r in results]
        
        bullish_count = sum(1 for r in results if r.get("price_change_1d_pct", 0) > 0)
        bearish_count = len(results) - bullish_count
        
        return {
            "avg_opportunity_score": round(np.mean(scores), 2),
            "max_opportunity_score": round(max(scores), 2),
            "avg_volume_spike": round(np.mean(volume_spikes), 2),
            "avg_price_change_pct": round(np.mean(price_changes), 2),
            "sentiment": "bullish" if bullish_count > bearish_count else "bearish",
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
        }

    def _calculate_scan_confidence(self, valid_results: list, total_scanned: int) -> float:
        """Calculate confidence score for the scan."""
        if total_scanned == 0:
            return 0.0
        
        # Data coverage
        coverage = len(valid_results) / total_scanned
        
        # Data quality (check for simulated data)
        live_data_count = sum(1 for r in valid_results if not r.get("simulated", True))
        data_quality = live_data_count / len(valid_results) if valid_results else 0
        
        # Sample size adequacy
        sample_score = min(len(valid_results) / 10, 1.0)
        
        confidence = (coverage * 0.3 + data_quality * 0.4 + sample_score * 0.3)
        return round(min(confidence, 0.95), 3)

    def _determine_recommendation(self, top_opportunities: list) -> str:
        """Determine overall recommendation from scan results."""
        if not top_opportunities:
            return "NO_TRADE"
        
        # If top opportunities have high scores, recommend scanning
        avg_top_score = np.mean([o.get("opportunity_score", 0) for o in top_opportunities[:3]])
        
        if avg_top_score >= 60:
            return "SCAN_ACTIVE"
        elif avg_top_score >= 40:
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
async def run_market_scan(
    tickers: Optional[list] = None,
    criteria: Optional[dict] = None,
    max_results: int = 10,
) -> dict:
    """Run market scan directly."""
    agent = MarketScannerAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"scanner-direct-{datetime.now(timezone.utc).timestamp()}",
        agent_type="market_scanner",
        payload={
            "tickers": tickers,
            "criteria": criteria,
            "max_results": max_results,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
