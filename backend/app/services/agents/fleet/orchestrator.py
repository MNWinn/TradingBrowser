"""
Fleet Orchestrator - Coordinates multiple market research agents simultaneously.

This orchestrator manages the fleet of specialized market research agents,
allowing parallel execution and consensus building across different
analysis dimensions.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum

from app.services.agents.base import BaseAgent, AgentTask, AgentOutput, AgentStatus
from app.services.agents.fleet import (
    MiroFishAssessmentAgent,
    MarketScannerAgent,
    PatternRecognitionAgent,
    MomentumAgent,
    SupportResistanceAgent,
    VolumeProfileAgent,
)
from app.core.database import SessionLocal
from app.models.entities import SwarmAgentRun, SwarmConsensusOutput


class FleetStrategy(Enum):
    """Execution strategies for the fleet."""
    SEQUENTIAL = "sequential"  # Run agents one by one
    PARALLEL = "parallel"      # Run all agents simultaneously
    PRIORITY = "priority"      # Run high-confidence agents first
    ADAPTIVE = "adaptive"      # Adapt based on initial results


@dataclass
class FleetResult:
    """Result from a fleet execution."""
    task_id: str
    ticker: str
    strategy: FleetStrategy
    agent_results: List[dict]
    consensus: dict
    execution_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FleetOrchestrator:
    """
    Orchestrates the fleet of market research agents.
    
    Features:
    - Parallel agent execution
    - Consensus building across agents
    - Configurable execution strategies
    - Result aggregation and ranking
    - Confidence-weighted recommendations
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_strategy: FleetStrategy = FleetStrategy.PARALLEL,
    ):
        self.redis_client = redis_client
        self.default_strategy = default_strategy
        self.agents: Dict[str, type] = {
            "mirofish_assessment": MiroFishAssessmentAgent,
            "market_scanner": MarketScannerAgent,
            "pattern_recognition": PatternRecognitionAgent,
            "momentum": MomentumAgent,
            "support_resistance": SupportResistanceAgent,
            "volume_profile": VolumeProfileAgent,
        }
        self._active_agents: Dict[str, BaseAgent] = {}

    async def initialize(self) -> None:
        """Initialize the orchestrator and all fleet agents."""
        for agent_type, agent_class in self.agents.items():
            agent = agent_class(
                agent_id=f"{agent_type}-fleet",
                redis_client=self.redis_client,
            )
            await agent.initialize()
            self._active_agents[agent_type] = agent

    async def shutdown(self) -> None:
        """Shutdown all fleet agents."""
        for agent in self._active_agents.values():
            await agent.shutdown()
        self._active_agents.clear()

    async def run_fleet(
        self,
        ticker: str,
        agents: Optional[List[str]] = None,
        strategy: Optional[FleetStrategy] = None,
        payload: Optional[dict] = None,
    ) -> FleetResult:
        """
        Run the fleet of agents against a ticker.
        
        Args:
            ticker: Stock symbol to analyze
            agents: List of agent types to run (None = all)
            strategy: Execution strategy (None = default)
            payload: Additional parameters for agents
            
        Returns:
            FleetResult with all agent outputs and consensus
        """
        start_time = datetime.now(timezone.utc)
        task_id = f"fleet-{ticker}-{uuid.uuid4().hex[:8]}"
        
        # Determine which agents to run
        agents_to_run = agents or list(self.agents.keys())
        exec_strategy = strategy or self.default_strategy
        
        # Build base payload
        base_payload = {"ticker": ticker, **(payload or {})}
        
        # Execute based on strategy
        if exec_strategy == FleetStrategy.PARALLEL:
            results = await self._run_parallel(task_id, agents_to_run, base_payload)
        elif exec_strategy == FleetStrategy.SEQUENTIAL:
            results = await self._run_sequential(task_id, agents_to_run, base_payload)
        elif exec_strategy == FleetStrategy.PRIORITY:
            results = await self._run_priority(task_id, agents_to_run, base_payload)
        else:  # ADAPTIVE
            results = await self._run_adaptive(task_id, agents_to_run, base_payload)
        
        # Calculate execution time
        execution_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        # Build consensus
        consensus = self._build_consensus(results, ticker)
        
        # Create fleet result
        fleet_result = FleetResult(
            task_id=task_id,
            ticker=ticker,
            strategy=exec_strategy,
            agent_results=results,
            consensus=consensus,
            execution_time_ms=round(execution_time_ms, 2),
        )
        
        # Store results
        await self._store_fleet_results(fleet_result)
        
        return fleet_result

    async def _run_parallel(
        self,
        task_id: str,
        agents: List[str],
        payload: dict
    ) -> List[dict]:
        """Run all agents in parallel."""
        tasks = []
        
        for agent_type in agents:
            if agent_type in self._active_agents:
                agent = self._active_agents[agent_type]
                task = AgentTask(
                    task_id=f"{task_id}-{agent_type}",
                    agent_type=agent_type,
                    payload=payload,
                )
                tasks.append(self._execute_agent_safe(agent, task))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out errors
        valid_results = []
        for r in results:
            if isinstance(r, dict) and "error" not in r:
                valid_results.append(r)
            elif isinstance(r, Exception):
                valid_results.append({"error": str(r), "agent": "unknown"})
            else:
                valid_results.append(r)
        
        return valid_results

    async def _run_sequential(
        self,
        task_id: str,
        agents: List[str],
        payload: dict
    ) -> List[dict]:
        """Run agents one at a time."""
        results = []
        
        for agent_type in agents:
            if agent_type in self._active_agents:
                agent = self._active_agents[agent_type]
                task = AgentTask(
                    task_id=f"{task_id}-{agent_type}",
                    agent_type=agent_type,
                    payload=payload,
                )
                result = await self._execute_agent_safe(agent, task)
                results.append(result)
        
        return results

    async def _run_priority(
        self,
        task_id: str,
        agents: List[str],
        payload: dict
    ) -> List[dict]:
        """Run high-priority agents first, then others if needed."""
        # Priority order
        priority_order = [
            "mirofish_assessment",
            "momentum",
            "support_resistance",
            "volume_profile",
            "pattern_recognition",
            "market_scanner",
        ]
        
        # Sort agents by priority
        sorted_agents = sorted(
            agents,
            key=lambda a: priority_order.index(a) if a in priority_order else 999
        )
        
        results = []
        
        # Run first 3 agents
        for agent_type in sorted_agents[:3]:
            if agent_type in self._active_agents:
                agent = self._active_agents[agent_type]
                task = AgentTask(
                    task_id=f"{task_id}-{agent_type}",
                    agent_type=agent_type,
                    payload=payload,
                )
                result = await self._execute_agent_safe(agent, task)
                results.append(result)
        
        # Check if we have high confidence
        high_conf_count = sum(
            1 for r in results 
            if isinstance(r, dict) and r.get("confidence", 0) > 0.7
        )
        
        # If low confidence, run remaining agents
        if high_conf_count < 2 and len(sorted_agents) > 3:
            for agent_type in sorted_agents[3:]:
                if agent_type in self._active_agents:
                    agent = self._active_agents[agent_type]
                    task = AgentTask(
                        task_id=f"{task_id}-{agent_type}",
                        agent_type=agent_type,
                        payload=payload,
                    )
                    result = await self._execute_agent_safe(agent, task)
                    results.append(result)
        
        return results

    async def _run_adaptive(
        self,
        task_id: str,
        agents: List[str],
        payload: dict
    ) -> List[dict]:
        """Adapt execution based on initial results."""
        # Start with core agents
        core_agents = ["momentum", "support_resistance", "volume_profile"]
        core_results = await self._run_parallel(task_id, core_agents, payload)
        
        # Analyze initial results
        bullish_signals = 0
        bearish_signals = 0
        
        for result in core_results:
            if isinstance(result, dict):
                rec = result.get("recommendation", "")
                if "LONG" in rec:
                    bullish_signals += 1
                elif "SHORT" in rec:
                    bearish_signals += 1
        
        # Adapt remaining agents based on direction
        remaining = [a for a in agents if a not in core_agents]
        
        if bullish_signals >= 2:
            # Focus on confirmation agents
            payload["bias"] = "bullish"
        elif bearish_signals >= 2:
            payload["bias"] = "bearish"
        
        if remaining:
            remaining_results = await self._run_parallel(task_id, remaining, payload)
            core_results.extend(remaining_results)
        
        return core_results

    async def _execute_agent_safe(self, agent: BaseAgent, task: AgentTask) -> dict:
        """Execute an agent with error handling."""
        try:
            output = await agent.execute(task)
            if output.result:
                return output.result
            return {"error": "No result", "agent": agent.agent_type}
        except Exception as e:
            return {
                "error": str(e),
                "agent": agent.agent_type,
                "agent_id": agent.agent_id,
            }

    def _build_consensus(self, results: List[dict], ticker: str) -> dict:
        """Build consensus from agent results."""
        if not results:
            return {
                "ticker": ticker,
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
                "agreement_score": 0.0,
                "agent_count": 0,
            }
        
        # Collect recommendations and confidences
        recommendations = []
        confidences = []
        
        for result in results:
            if isinstance(result, dict) and "error" not in result:
                rec = result.get("recommendation", "WATCHLIST")
                conf = result.get("confidence", 0.5)
                recommendations.append(rec)
                confidences.append(conf)
        
        if not recommendations:
            return {
                "ticker": ticker,
                "recommendation": "NO_TRADE",
                "confidence": 0.0,
                "agreement_score": 0.0,
                "agent_count": len(results),
            }
        
        # Count recommendations
        rec_counts = {}
        for rec in recommendations:
            # Normalize recommendations
            normalized = self._normalize_recommendation(rec)
            rec_counts[normalized] = rec_counts.get(normalized, 0) + 1
        
        # Find dominant recommendation
        dominant_rec = max(rec_counts, key=rec_counts.get)
        dominant_count = rec_counts[dominant_rec]
        
        # Calculate agreement score
        agreement_score = dominant_count / len(recommendations)
        
        # Calculate weighted confidence
        avg_confidence = sum(confidences) / len(confidences)
        weighted_confidence = avg_confidence * (0.5 + 0.5 * agreement_score)
        
        # Determine final recommendation
        if agreement_score >= 0.6 and weighted_confidence >= 0.6:
            final_rec = dominant_rec
        elif agreement_score >= 0.4 and weighted_confidence >= 0.5:
            final_rec = f"WATCHLIST_{dominant_rec}" if dominant_rec in ["LONG", "SHORT"] else "WATCHLIST"
        else:
            final_rec = "NO_TRADE"
        
        return {
            "ticker": ticker,
            "recommendation": final_rec,
            "confidence": round(min(weighted_confidence, 0.95), 3),
            "agreement_score": round(agreement_score, 3),
            "agent_count": len(results),
            "recommendation_breakdown": rec_counts,
            "avg_agent_confidence": round(avg_confidence, 3),
        }

    def _normalize_recommendation(self, rec: str) -> str:
        """Normalize recommendation to standard values."""
        rec_upper = str(rec).upper()
        
        if "LONG" in rec_upper and "SHORT" not in rec_upper:
            return "LONG"
        elif "SHORT" in rec_upper and "LONG" not in rec_upper:
            return "SHORT"
        elif "WATCHLIST" in rec_upper:
            return "WATCHLIST"
        else:
            return "NO_TRADE"

    async def _store_fleet_results(self, fleet_result: FleetResult) -> None:
        """Store fleet execution results in database."""
        try:
            db = SessionLocal()
            try:
                # Store individual agent runs
                for agent_result in fleet_result.agent_results:
                    if isinstance(agent_result, dict) and "error" not in agent_result:
                        run = SwarmAgentRun(
                            task_id=fleet_result.task_id,
                            agent_name=agent_result.get("agent", "unknown"),
                            recommendation=agent_result.get("recommendation"),
                            confidence=agent_result.get("confidence"),
                            output=agent_result,
                        )
                        db.add(run)
                
                # Store consensus
                consensus = SwarmConsensusOutput(
                    task_id=fleet_result.task_id,
                    ticker=fleet_result.ticker,
                    aggregated_recommendation=fleet_result.consensus.get("recommendation"),
                    consensus_score=fleet_result.consensus.get("confidence"),
                    disagreement_score=1 - fleet_result.consensus.get("agreement_score", 0),
                    explanation=f"Fleet execution with {fleet_result.consensus.get('agent_count', 0)} agents using {fleet_result.strategy.value} strategy",
                )
                db.add(consensus)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"Failed to store fleet results: {e}")

    def get_agent_info(self) -> dict:
        """Get information about available agents in the fleet."""
        return {
            "available_agents": list(self.agents.keys()),
            "active_agents": list(self._active_agents.keys()),
            "default_strategy": self.default_strategy.value,
            "strategies": [s.value for s in FleetStrategy],
        }


# Singleton instance
_fleet_orchestrator: Optional[FleetOrchestrator] = None


def get_fleet_orchestrator() -> FleetOrchestrator:
    """Get or create the singleton fleet orchestrator instance."""
    global _fleet_orchestrator
    if _fleet_orchestrator is None:
        _fleet_orchestrator = FleetOrchestrator()
    return _fleet_orchestrator


async def initialize_fleet() -> FleetOrchestrator:
    """Initialize the fleet orchestrator singleton."""
    orchestrator = get_fleet_orchestrator()
    await orchestrator.initialize()
    return orchestrator


async def shutdown_fleet() -> None:
    """Shutdown the fleet orchestrator singleton."""
    global _fleet_orchestrator
    if _fleet_orchestrator:
        await _fleet_orchestrator.shutdown()
        _fleet_orchestrator = None


# Convenience function for direct usage
async def run_fleet_analysis(
    ticker: str,
    agents: Optional[List[str]] = None,
    strategy: str = "parallel",
) -> dict:
    """
    Run fleet analysis directly.
    
    Args:
        ticker: Stock symbol to analyze
        agents: List of agent types to run (None = all)
        strategy: Execution strategy ("parallel", "sequential", "priority", "adaptive")
        
    Returns:
        Fleet analysis results dict
    """
    orchestrator = FleetOrchestrator()
    await orchestrator.initialize()
    
    strategy_enum = FleetStrategy(strategy)
    result = await orchestrator.run_fleet(ticker, agents, strategy_enum)
    
    await orchestrator.shutdown()
    
    return {
        "task_id": result.task_id,
        "ticker": result.ticker,
        "strategy": result.strategy.value,
        "execution_time_ms": result.execution_time_ms,
        "consensus": result.consensus,
        "agent_results": result.agent_results,
        "timestamp": result.timestamp,
    }
