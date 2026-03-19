"""
Agent Orchestrator Service for TradingBrowser.

Manages agent lifecycle, task queues, shared memory coordination,
and health tracking for distributed agent execution.
"""

from .base import BaseAgent, AgentStatus, AgentTask, AgentOutput
from .orchestrator import AgentOrchestrator, get_orchestrator
from .technical_analysis import (
    technical_analysis_agent,
    run_technical_analysis,
    calculate_rsi,
    calculate_macd,
    calculate_vwap,
    calculate_bollinger_bands,
)

# Fleet of Market Research Agents
from .fleet import (
    MiroFishAssessmentAgent,
    MarketScannerAgent,
    PatternRecognitionAgent,
    MomentumAgent,
    SupportResistanceAgent,
    VolumeProfileAgent,
)
from .fleet.orchestrator import (
    FleetOrchestrator,
    FleetStrategy,
    get_fleet_orchestrator,
    initialize_fleet,
    shutdown_fleet,
    run_fleet_analysis,
)

__all__ = [
    "BaseAgent",
    "AgentStatus",
    "AgentTask",
    "AgentOutput",
    "AgentOrchestrator",
    "get_orchestrator",
    "technical_analysis_agent",
    "run_technical_analysis",
    "calculate_rsi",
    "calculate_macd",
    "calculate_vwap",
    "calculate_bollinger_bands",
    # Fleet Agents
    "MiroFishAssessmentAgent",
    "MarketScannerAgent",
    "PatternRecognitionAgent",
    "MomentumAgent",
    "SupportResistanceAgent",
    "VolumeProfileAgent",
    # Fleet Orchestrator
    "FleetOrchestrator",
    "FleetStrategy",
    "get_fleet_orchestrator",
    "initialize_fleet",
    "shutdown_fleet",
    "run_fleet_analysis",
]