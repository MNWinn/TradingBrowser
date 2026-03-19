"""
Trading System - Main Orchestrator

Integrates all 9 agents into a cohesive trading research architecture.
Provides high-level API for running the system and conducting research.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np

from .message_bus import MessageBus, get_message_bus
from .market_structure_agent import MarketStructureAgent, MarketRegime
from .mirofish_signal_agent import MiroFishSignalAgent
from .research_agent import ResearchAgent
from .strategy_agent import StrategyAgent
from .risk_agent import RiskAgent
from .execution_simulation_agent import ExecutionSimulationAgent
from .evaluation_agent import EvaluationAgent
from .memory_learning_agent import MemoryLearningAgent
from .supervisor_agent import SupervisorAgent, SystemMode


class TradingSystem:
    """
    Main trading system that orchestrates all 9 agents.
    
    Architecture:
    1. MarketStructureAgent - Analyzes price action and regimes
    2. MiroFishSignalAgent - Ingests predictive signals
    3. ResearchAgent - Tests hypotheses systematically
    4. StrategyAgent - Combines signals into trade ideas
    5. RiskAgent - Approves/rejects trades
    6. ExecutionSimulationAgent - Paper trades approved setups
    7. EvaluationAgent - Studies results across many trades
    8. MemoryLearningAgent - Stores lessons and updates beliefs
    9. SupervisorAgent - Orchestrates all agents
    
    Flow:
    Market Data -> MarketStructureAgent + MiroFishSignalAgent
         |
         v
    StrategyAgent (combines signals)
         |
         v
    RiskAgent (validates risk)
         |
         v
    ExecutionSimulationAgent (paper trades)
         |
         v
    EvaluationAgent + MemoryLearningAgent (learn)
         |
         v
    ResearchAgent (generates new hypotheses)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.message_bus = get_message_bus()
        
        # Create agents
        self.agents = {
            "market_structure": MarketStructureAgent(self.message_bus, self.config.get("market_structure")),
            "mirofish_signal": MiroFishSignalAgent(self.message_bus, self.config.get("mirofish_signal")),
            "research": ResearchAgent(self.message_bus, self.config.get("research")),
            "strategy": StrategyAgent(self.message_bus, self.config.get("strategy")),
            "risk": RiskAgent(self.message_bus, self.config.get("risk")),
            "execution_simulation": ExecutionSimulationAgent(self.message_bus, self.config.get("execution_simulation")),
            "evaluation": EvaluationAgent(self.message_bus, self.config.get("evaluation")),
            "memory_learning": MemoryLearningAgent(self.message_bus, self.config.get("memory_learning")),
            "supervisor": SupervisorAgent(self.message_bus, self.config.get("supervisor")),
        }
        
        self._running = False
        self._tasks = []
        
    async def start(self):
        """Start the trading system."""
        print("=" * 70)
        print("TRADING SYSTEM STARTING")
        print("=" * 70)
        
        # Start message bus
        await self.message_bus.start()
        
        # Register agents with supervisor
        for name, agent in self.agents.items():
            await self.agents["supervisor"].register_agent(name)
            
        # Start all agents
        for name, agent in self.agents.items():
            print(f"[SYSTEM] Starting {name} agent...")
            await agent.start()
            
        self._running = True
        
        print("=" * 70)
        print("ALL AGENTS STARTED")
        print("=" * 70)
        
    async def stop(self):
        """Stop the trading system."""
        print("[SYSTEM] Stopping trading system...")
        
        self._running = False
        
        # Stop all agents
        for name, agent in self.agents.items():
            await agent.stop()
            
        # Stop message bus
        await self.message_bus.stop()
        
        print("[SYSTEM] Trading system stopped")
        
    async def ingest_market_data(self, ticker: str, data: Dict[str, Any]):
        """Ingest market data into the system."""
        # Send to market structure agent
        await self.message_bus.publish(
            type("AgentMessage", (), {
                "msg_type": __import__(".message_bus", fromlist=["MessageType"]).MessageType.PRICE_ACTION_ALERT,
                "source": "external",
                "target": None,
                "payload": {
                    "ticker": ticker,
                    "price_data": data,
                },
                "timestamp": datetime.utcnow(),
                "msg_id": f"price_{datetime.utcnow().timestamp()}",
                "correlation_id": None,
                "priority": 5,
            })()
        )
        
    async def run_research_cycle(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete research cycle on a hypothesis."""
        
        # 1. Propose hypothesis
        result = await self.agents["research"].process_task({
            "type": "propose",
            "hypothesis": hypothesis,
        })
        
        hypothesis_id = result.get("hypothesis_id")
        
        # 2. Test hypothesis
        test_result = await self.agents["research"].process_task({
            "type": "test",
            "hypothesis_id": hypothesis_id,
        })
        
        return {
            "hypothesis_id": hypothesis_id,
            "propose_result": result,
            "test_result": test_result,
        }
        
    async def process_signal(self, ticker: str, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a signal through the system."""
        
        # 1. Ingest MiroFish signal
        await self.agents["mirofish_signal"].process_task({
            "type": "ingest",
            "ticker": ticker,
            "prediction": signal_data,
        })
        
        # 2. Generate proposal (handled by strategy agent via message bus)
        # Wait a moment for processing
        await asyncio.sleep(0.1)
        
        # 3. Check for proposals
        proposals = await self.agents["strategy"].process_task({
            "type": "get_active_proposals",
        })
        
        return proposals
        
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        
        supervisor_status = self.agents["supervisor"].get_status()
        
        agent_statuses = {}
        for name, agent in self.agents.items():
            agent_statuses[name] = agent.get_status()
            
        return {
            "supervisor": supervisor_status,
            "agents": agent_statuses,
            "message_bus": self.message_bus.get_stats(),
        }
        
    async def run_simulation(
        self, 
        tickers: List[str], 
        num_days: int = 30,
        trades_per_day: int = 5
    ) -> Dict[str, Any]:
        """
        Run a comprehensive simulation.
        
        Generates synthetic market data and runs trades through the system.
        """
        print(f"[SIMULATION] Running {num_days} day simulation on {len(tickers)} tickers")
        
        total_trades_target = num_days * trades_per_day
        trades_executed = 0
        
        # Generate synthetic market data and run through system
        for day in range(num_days):
            print(f"[SIMULATION] Day {day + 1}/{num_days}")
            
            for ticker in tickers:
                # Generate synthetic price data
                price_data = self._generate_synthetic_data(ticker, day)
                
                # Ingest into system
                await self.ingest_market_data(ticker, price_data)
                
                # Generate MiroFish-like signal
                signal = self._generate_synthetic_signal(ticker, price_data)
                await self.process_signal(ticker, signal)
                
            # Wait for processing
            await asyncio.sleep(0.05)
            
            # Count trades
            exec_status = await self.agents["execution_simulation"].process_task({
                "type": "get_metrics",
            })
            trades_executed = exec_status.get("metrics", {}).get("total_trades", 0)
            
        # Get final results
        exec_metrics = await self.agents["execution_simulation"].process_task({
            "type": "get_metrics",
        })
        
        return {
            "simulation_days": num_days,
            "tickers": tickers,
            "trades_executed": trades_executed,
            "execution_metrics": exec_metrics.get("metrics", {}),
        }
        
    def _generate_synthetic_data(self, ticker: str, day: int) -> Dict[str, Any]:
        """Generate synthetic OHLCV data."""
        base_price = 100 + hash(ticker) % 100
        volatility = 0.02
        
        # Random walk
        change = np.random.normal(0, volatility)
        close = base_price * (1 + change)
        
        return {
            "open": close * (1 + np.random.normal(0, 0.005)),
            "high": close * (1 + abs(np.random.normal(0, 0.01))),
            "low": close * (1 - abs(np.random.normal(0, 0.01))),
            "close": close,
            "volume": np.random.randint(1000000, 10000000),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    def _generate_synthetic_signal(self, ticker: str, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate synthetic MiroFish-like signal."""
        
        # Random direction with slight bullish bias
        r = np.random.random()
        if r > 0.55:
            bias = "BULLISH"
        elif r < 0.45:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
            
        confidence = 0.5 + np.random.random() * 0.4
        
        return {
            "directional_bias": bias,
            "confidence": confidence,
            "scenario_summary": f"Synthetic {bias.lower()} scenario for {ticker}",
            "catalyst_summary": "Synthetic catalyst",
            "risk_flags": [],
            "scenarios": [
                {"probability": confidence, "direction": bias},
                {"probability": 1 - confidence, "direction": "NEUTRAL"},
            ],
            "model_votes": {
                "bullish": 3 if bias == "BULLISH" else 1,
                "bearish": 3 if bias == "BEARISH" else 1,
                "neutral": 2 if bias == "NEUTRAL" else 1,
            },
        }
        
    async def get_evaluation_report(self, strategy_id: str = "default") -> Dict[str, Any]:
        """Get evaluation report for a strategy."""
        
        result = await self.agents["evaluation"].process_task({
            "type": "get_scorecard",
            "strategy_id": strategy_id,
        })
        
        return result
        
    async def get_lessons_learned(self) -> Dict[str, Any]:
        """Get lessons learned from memory agent."""
        
        result = await self.agents["memory_learning"].process_task({
            "type": "get_lessons",
        })
        
        return result


# Convenience function for creating and running the system
async def create_trading_system(config: Optional[Dict[str, Any]] = None) -> TradingSystem:
    """Create and initialize a trading system."""
    system = TradingSystem(config)
    await system.start()
    return system
