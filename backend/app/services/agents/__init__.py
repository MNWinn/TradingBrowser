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
]