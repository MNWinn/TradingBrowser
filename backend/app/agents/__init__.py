"""
9-Agent Trading Research Architecture

A sophisticated hypothesis-driven system for rigorous strategy validation.

Agents:
1. MarketStructureAgent - Analyze price action, volatility, trend, momentum, volume
2. MiroFishSignalAgent - Ingest MiroFish predictive outputs
3. ResearchAgent - Test strategy hypotheses
4. StrategyAgent - Combine signals and formulate trade ideas
5. RiskAgent - Reject poor trades and enforce limits
6. ExecutionSimulationAgent - Paper trade approved setups
7. EvaluationAgent - Study results across hundreds of trades
8. MemoryLearningAgent - Store lessons from wins/losses
9. SupervisorAgent - Orchestrate all sub-agents
"""

from .base_agent import BaseAgent, AgentState, AgentMessage
from .message_bus import MessageBus, MessageType
from .market_structure_agent import MarketStructureAgent
from .mirofish_signal_agent import MiroFishSignalAgent
from .research_agent import ResearchAgent
from .strategy_agent import StrategyAgent
from .risk_agent import RiskAgent
from .execution_simulation_agent import ExecutionSimulationAgent
from .evaluation_agent import EvaluationAgent
from .memory_learning_agent import MemoryLearningAgent
from .supervisor_agent import SupervisorAgent
from .trading_system import TradingSystem

__all__ = [
    "BaseAgent",
    "AgentState", 
    "AgentMessage",
    "MessageBus",
    "MessageType",
    "MarketStructureAgent",
    "MiroFishSignalAgent",
    "ResearchAgent",
    "StrategyAgent",
    "RiskAgent",
    "ExecutionSimulationAgent",
    "EvaluationAgent",
    "MemoryLearningAgent",
    "SupervisorAgent",
    "TradingSystem",
]
