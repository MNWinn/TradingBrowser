"""
MiroFish Assessment Agent - Deep multi-timeframe MiroFish analysis.

This agent performs comprehensive MiroFish analysis across multiple timeframes
and lenses to provide deep market intelligence with confidence scoring.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.mirofish import mirofish_deep_swarm, mirofish_predict
from app.services.focus_runtime import is_focus_ticker
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun


class MiroFishAssessmentAgent(BaseAgent):
    """
    Deep MiroFish analysis agent with multi-timeframe capabilities.
    
    Specialization:
    - Multi-timeframe narrative analysis (1m, 5m, 15m, 1h, 1d)
    - Multi-lens assessment (trend, momentum, catalyst, risk, sentiment)
    - Focus ticker deep-dive with extended analysis
    - Confidence scoring based on alignment across timeframes
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        redis_client: Optional[Any] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        super().__init__(
            agent_id=agent_id or "mirofish_assessment",
            agent_type="mirofish_assessment",
            redis_client=redis_client,
            heartbeat_interval_sec=heartbeat_interval_sec,
            timeout_sec=timeout_sec,
        )
        self.specialization = "deep_narrative_analysis"
        self.timeframes = ["1m", "5m", "15m", "1h", "1d"]
        self.lenses = ["trend", "momentum", "catalyst", "risk", "sentiment"]

    async def _run(self, payload: dict) -> dict:
        """
        Execute deep MiroFish assessment.
        
        Args:
            payload: Must contain 'ticker'. Optional: 'timeframes', 'lenses', 'deep_mode'
            
        Returns:
            Dict with comprehensive MiroFish analysis and confidence scoring
        """
        ticker = payload.get("ticker", "").upper()
        if not ticker:
            raise ValueError("ticker is required in payload")

        deep_mode = payload.get("deep_mode", True)
        custom_timeframes = payload.get("timeframes")
        custom_lenses = payload.get("lenses")
        
        self.log(f"Starting MiroFish assessment for {ticker}", "info")
        
        # Determine analysis depth based on focus status
        is_focus = is_focus_ticker(ticker)
        
        if deep_mode or is_focus:
            # Deep analysis with multiple timeframes and lenses
            result = await mirofish_deep_swarm({
                "ticker": ticker,
                "timeframes": custom_timeframes or (self.timeframes if is_focus else ["5m", "15m", "1h", "1d"]),
                "lenses": custom_lenses or (self.lenses if is_focus else ["trend", "momentum", "risk"]),
                "focus_context": payload.get("focus_context", "priority" if is_focus else "")
            })
        else:
            # Standard single analysis
            result = await mirofish_predict({
                "ticker": ticker,
                "timeframe": payload.get("timeframe", "5m"),
                "lens": payload.get("lens", "overall")
            })
            # Convert to deep format for consistency
            result = {
                "deep": False,
                "ticker": ticker,
                "overall_bias": result.get("directional_bias", "NEUTRAL"),
                "overall_confidence": result.get("confidence", 0.5),
                "analyses": [{
                    "timeframe": payload.get("timeframe", "5m"),
                    "lens": payload.get("lens", "overall"),
                    "bias": result.get("directional_bias", "NEUTRAL"),
                    "confidence": result.get("confidence", 0.5),
                    "summary": result.get("scenario_summary", ""),
                    "catalyst": result.get("catalyst_summary", ""),
                    "risk_flags": result.get("risk_flags", []),
                }],
                "provider_mode": result.get("provider_mode", "unknown"),
            }

        # Calculate enhanced confidence score
        confidence_data = self._calculate_confidence(result)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(result, confidence_data)
        
        output = {
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "ticker": ticker,
            "recommendation": recommendation,
            "confidence": confidence_data["overall_confidence"],
            "confidence_breakdown": confidence_data,
            "mirofish_data": result,
            "analysis_depth": "deep" if result.get("deep") else "standard",
            "timeframes_analyzed": len(result.get("analyses", [])),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self.log(f"Completed MiroFish assessment for {ticker}: {recommendation} (confidence: {confidence_data['overall_confidence']})", "info")
        
        # Store results in database
        await self._store_results(output)
        
        return output

    def _calculate_confidence(self, result: dict) -> dict:
        """Calculate comprehensive confidence score from MiroFish results."""
        analyses = result.get("analyses", [])
        
        if not analyses:
            return {
                "overall_confidence": 0.5,
                "alignment_score": 0.0,
                "source_reliability": 0.5,
                "timeframe_coverage": 0.0,
            }
        
        # Alignment score - how many analyses agree
        votes = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
        for a in analyses:
            bias = a.get("bias", "NEUTRAL")
            votes[bias] = votes.get(bias, 0) + 1
        
        dominant_bias = max(votes, key=votes.get)
        alignment_score = votes[dominant_bias] / len(analyses)
        
        # Source reliability based on provider mode
        provider_mode = result.get("provider_mode", "unknown")
        if provider_mode.startswith("live"):
            source_reliability = 0.9
        elif provider_mode == "stub":
            source_reliability = 0.5
        else:
            source_reliability = 0.7
        
        # Timeframe coverage
        timeframe_coverage = min(len(analyses) / 5, 1.0)  # Max at 5 timeframes
        
        # Calculate overall confidence
        base_confidence = result.get("overall_confidence", 0.5)
        overall_confidence = (
            base_confidence * 0.4 +
            alignment_score * 0.3 +
            source_reliability * 0.2 +
            timeframe_coverage * 0.1
        )
        
        return {
            "overall_confidence": round(min(overall_confidence, 0.95), 3),
            "alignment_score": round(alignment_score, 3),
            "source_reliability": round(source_reliability, 3),
            "timeframe_coverage": round(timeframe_coverage, 3),
            "dominant_bias": dominant_bias,
            "vote_distribution": votes,
        }

    def _determine_recommendation(self, result: dict, confidence_data: dict) -> str:
        """Determine trading recommendation from analysis."""
        bias = result.get("overall_bias", "NEUTRAL")
        confidence = confidence_data["overall_confidence"]
        alignment = confidence_data["alignment_score"]
        
        # High confidence + strong alignment = direct trade signal
        if confidence >= 0.75 and alignment >= 0.7:
            if bias == "BULLISH":
                return "LONG"
            elif bias == "BEARISH":
                return "SHORT"
        
        # Medium confidence = watchlist
        if confidence >= 0.55 and alignment >= 0.5:
            return "WATCHLIST"
        
        # Low confidence or mixed signals = no trade
        return "NO_TRADE"

    async def _store_results(self, output: dict) -> None:
        """Store agent results in database."""
        try:
            db = SessionLocal()
            try:
                run = SwarmAgentRun(
                    task_id=output.get("task_id", f"{self.agent_id}-{datetime.now(timezone.utc).timestamp()}"),
                    agent_name=self.agent_type,
                    recommendation=output.get("recommendation"),
                    confidence=output.get("confidence"),
                    output=output,
                )
                db.add(run)
                db.commit()
                self.log(f"Stored results for {output.get('ticker')}", "info")
            finally:
                db.close()
        except Exception as e:
            self.log(f"Failed to store results: {e}", "error")


# Convenience function for direct usage
async def run_mirofish_assessment(
    ticker: str,
    deep_mode: bool = True,
    timeframes: Optional[list] = None,
    lenses: Optional[list] = None,
) -> dict:
    """
    Run MiroFish assessment directly without agent lifecycle.
    
    Args:
        ticker: Stock symbol to analyze
        deep_mode: Whether to perform deep multi-timeframe analysis
        timeframes: Optional list of timeframes to analyze
        lenses: Optional list of analysis lenses
        
    Returns:
        Assessment results dict
    """
    agent = MiroFishAssessmentAgent()
    await agent.initialize()
    
    task = AgentTask(
        task_id=f"mirofish-direct-{ticker}-{datetime.now(timezone.utc).timestamp()}",
        agent_type="mirofish_assessment",
        payload={
            "ticker": ticker,
            "deep_mode": deep_mode,
            "timeframes": timeframes,
            "lenses": lenses,
        },
    )
    
    output = await agent.execute(task)
    await agent.shutdown()
    
    return output.result
