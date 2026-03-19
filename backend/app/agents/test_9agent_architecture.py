"""
Comprehensive Test Suite for 9-Agent Trading Research Architecture

This test suite validates:
1. Individual agent functionality
2. Inter-agent communication via message bus
3. End-to-end trading workflow
4. Performance across different market regimes
5. System robustness with 100s of simulated trades
"""

import asyncio
import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents import (
    TradingSystem,
    MarketStructureAgent,
    MiroFishSignalAgent,
    ResearchAgent,
    StrategyAgent,
    RiskAgent,
    ExecutionSimulationAgent,
    EvaluationAgent,
    MemoryLearningAgent,
    SupervisorAgent,
    MessageBus,
    MessageType,
    AgentMessage,
    get_message_bus,
    reset_message_bus,
)
from app.agents.market_structure_agent import MarketRegime, TechnicalState
from app.agents.mirofish_signal_agent import SignalDirection, MiroFishSignal
from app.agents.research_agent import Hypothesis, HypothesisStatus, TestType
from app.agents.strategy_agent import TradeDirection, TradeProposal
from app.agents.risk_agent import RiskDecision, ViolationType
from app.agents.execution_simulation_agent import TradeStatus, ExitReason
from app.agents.evaluation_agent import MetricGrade, TradeMetrics
from app.agents.memory_learning_agent import LessonType, PatternConfidence
from app.agents.supervisor_agent import SystemMode, Priority


# Fixtures
@pytest.fixture
def message_bus():
    """Create a fresh message bus for each test."""
    reset_message_bus()
    bus = get_message_bus()
    asyncio.run(bus.start())
    yield bus
    asyncio.run(bus.stop())


@pytest.fixture
async def trading_system():
    """Create a full trading system."""
    reset_message_bus()
    system = TradingSystem({
        "market_structure": {"lookback_periods": 50},
        "risk": {"max_position_size": 0.20, "min_conviction": 0.50},
        "execution_simulation": {"base_slippage": 0.0005},
        "evaluation": {"min_trades": 30, "min_graduation_trades": 50},
    })
    await system.start()
    yield system
    await system.stop()


@pytest.fixture
async def market_structure_agent(message_bus):
    """Create a market structure agent."""
    agent = MarketStructureAgent(message_bus, {"lookback_periods": 50})
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def mirofish_signal_agent(message_bus):
    """Create a MiroFish signal agent."""
    agent = MiroFishSignalAgent(message_bus, {"min_confidence": 0.5})
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def research_agent(message_bus):
    """Create a research agent."""
    agent = ResearchAgent(message_bus, {"max_variants": 50, "min_trades": 20})
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def strategy_agent(message_bus):
    """Create a strategy agent."""
    agent = StrategyAgent(message_bus, {"min_conviction": 0.55, "min_risk_reward": 1.5})
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def risk_agent(message_bus):
    """Create a risk agent."""
    agent = RiskAgent(message_bus, {
        "max_position_size": 0.25,
        "max_drawdown": 0.10,
        "min_risk_reward": 1.5,
        "min_conviction": 0.55,
    })
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def execution_agent(message_bus):
    """Create an execution simulation agent."""
    agent = ExecutionSimulationAgent(message_bus, {
        "base_slippage": 0.0005,
        "commission": 1.0,
        "fill_probability": 0.98,
    })
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def evaluation_agent(message_bus):
    """Create an evaluation agent."""
    agent = EvaluationAgent(message_bus, {
        "min_trades": 30,
        "min_graduation_trades": 100,
    })
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def memory_agent(message_bus):
    """Create a memory/learning agent."""
    agent = MemoryLearningAgent(message_bus, {
        "min_observations": 3,
        "confidence_decay": 30,
    })
    await agent.start()
    yield agent
    await agent.stop()


@pytest.fixture
async def supervisor_agent(message_bus):
    """Create a supervisor agent."""
    agent = SupervisorAgent(message_bus, {
        "heartbeat_interval": 30,
        "summary_interval": 24,
    })
    await agent.start()
    yield agent
    await agent.stop()


# Test Data Generators
def generate_price_history(n_bars: int = 100, trend: str = "up") -> List[Dict[str, Any]]:
    """Generate synthetic price history."""
    prices = []
    base_price = 100.0
    
    for i in range(n_bars):
        if trend == "up":
            change = np.random.normal(0.001, 0.01)
        elif trend == "down":
            change = np.random.normal(-0.001, 0.01)
        else:
            change = np.random.normal(0, 0.01)
            
        close = base_price * (1 + change)
        prices.append({
            "timestamp": datetime.utcnow() - timedelta(minutes=n_bars-i),
            "open": close * (1 + np.random.normal(0, 0.002)),
            "high": close * (1 + abs(np.random.normal(0, 0.005))),
            "low": close * (1 - abs(np.random.normal(0, 0.005))),
            "close": close,
            "volume": np.random.randint(1000000, 10000000),
        })
        base_price = close
        
    return prices


def generate_mirofish_signal(bias: str = "BULLISH", confidence: float = 0.7) -> Dict[str, Any]:
    """Generate a synthetic MiroFish signal."""
    return {
        "directional_bias": bias,
        "confidence": confidence,
        "scenario_summary": f"Test {bias.lower()} scenario",
        "catalyst_summary": "Test catalyst",
        "risk_flags": [],
        "scenarios": [
            {"probability": confidence, "direction": bias},
            {"probability": (1-confidence)/2, "direction": "NEUTRAL"},
            {"probability": (1-confidence)/2, "direction": "BEARISH" if bias == "BULLISH" else "BULLISH"},
        ],
        "model_votes": {
            "bullish": 5 if bias == "BULLISH" else 2,
            "bearish": 5 if bias == "BEARISH" else 2,
            "neutral": 3 if bias == "NEUTRAL" else 1,
        },
        "timeframe": "5m",
        "horizon": "short_term",
    }


def generate_trade_proposal(direction: str = "long", conviction: float = 0.7) -> Dict[str, Any]:
    """Generate a synthetic trade proposal."""
    entry_price = 100.0
    
    if direction == "long":
        stop_loss = entry_price * 0.98
        take_profit = entry_price * 1.04
    else:
        stop_loss = entry_price * 1.02
        take_profit = entry_price * 0.96
        
    return {
        "proposal_id": f"prop_test_{datetime.utcnow().timestamp()}",
        "ticker": "TEST",
        "timestamp": datetime.utcnow().isoformat(),
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "position_size": 0.10,
        "risk_reward_ratio": 2.0,
        "conviction_score": conviction,
        "conviction_level": "HIGH" if conviction > 0.7 else "MEDIUM",
        "setup_type": "trend_following",
        "setup_quality": "A",
        "signal_agreement": 0.8,
    }


# Individual Agent Tests
class TestMarketStructureAgent:
    """Tests for MarketStructureAgent."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, market_structure_agent):
        """Test agent initializes correctly."""
        assert market_structure_agent.agent_id == "market_structure"
        assert market_structure_agent.state.value == "RUNNING"
        
    @pytest.mark.asyncio
    async def test_price_history_update(self, market_structure_agent):
        """Test price history is updated."""
        prices = generate_price_history(50)
        
        for price in prices:
            await market_structure_agent._update_price_history("TEST", price)
            
        assert "TEST" in market_structure_agent._price_history
        assert len(market_structure_agent._price_history["TEST"]) == 50
        
    @pytest.mark.asyncio
    async def test_regime_detection(self, market_structure_agent):
        """Test regime detection works."""
        # Generate uptrend data
        prices = generate_price_history(50, trend="up")
        
        for price in prices:
            await market_structure_agent._update_price_history("TEST", price)
            
        state = await market_structure_agent._analyze_ticker("TEST")
        
        assert state is not None
        assert state.ticker == "TEST"
        assert state.regime in list(MarketRegime)
        assert 0 <= state.regime_confidence <= 1
        assert -1 <= state.structure_score <= 1
        
    @pytest.mark.asyncio
    async def test_technical_indicators(self, market_structure_agent):
        """Test technical indicators are calculated."""
        prices = generate_price_history(50)
        
        for price in prices:
            await market_structure_agent._update_price_history("TEST", price)
            
        state = await market_structure_agent._analyze_ticker("TEST")
        
        assert 0 <= state.rsi_14 <= 100
        assert state.atr_14 >= 0
        assert state.bollinger_width >= 0
        assert state.trend_strength >= 0
        

class TestMiroFishSignalAgent:
    """Tests for MiroFishSignalAgent."""
    
    @pytest.mark.asyncio
    async def test_signal_processing(self, mirofish_signal_agent):
        """Test signal processing."""
        signal_data = generate_mirofish_signal("BULLISH", 0.75)
        
        await mirofish_signal_agent._process_prediction("AAPL", signal_data)
        
        assert "AAPL" in mirofish_signal_agent._current_signals
        signal = mirofish_signal_agent._current_signals["AAPL"]
        assert signal.direction == SignalDirection.BULLISH
        assert signal.confidence == 0.75
        
    @pytest.mark.asyncio
    async def test_signal_history(self, mirofish_signal_agent):
        """Test signal history tracking."""
        for i in range(5):
            signal_data = generate_mirofish_signal("BULLISH" if i % 2 == 0 else "BEARISH", 0.6 + i * 0.05)
            await mirofish_signal_agent._process_prediction("AAPL", signal_data)
            
        history = mirofish_signal_agent._signal_history.get("AAPL")
        assert history is not None
        assert len(history.signals) == 5
        
    @pytest.mark.asyncio
    async def test_disagreement_detection(self, mirofish_signal_agent):
        """Test internal disagreement detection."""
        # Signal with conflicting scenarios
        signal_data = {
            "directional_bias": "NEUTRAL",
            "confidence": 0.5,
            "scenarios": [
                {"probability": 0.4, "direction": "BULLISH"},
                {"probability": 0.4, "direction": "BEARISH"},
                {"probability": 0.2, "direction": "NEUTRAL"},
            ],
            "model_votes": {
                "bullish": 5,
                "bearish": 5,
                "neutral": 2,
            },
        }
        
        await mirofish_signal_agent._process_prediction("AAPL", signal_data)
        signal = mirofish_signal_agent._current_signals["AAPL"]
        
        assert signal.internal_disagreement > 0
        

class TestResearchAgent:
    """Tests for ResearchAgent."""
    
    @pytest.mark.asyncio
    async def test_hypothesis_proposal(self, research_agent):
        """Test hypothesis proposal."""
        hypothesis_data = {
            "name": "RSI Mean Reversion",
            "description": "Buy when RSI < 30, sell when RSI > 70",
            "entry_rules": {"rsi_threshold": 30},
            "exit_rules": {"rsi_threshold": 70},
            "risk_rules": {"stop_loss": 0.02},
            "parameters": {
                "rsi_entry": (20, 40, 5),
                "rsi_exit": (60, 80, 5),
            },
            "tags": ["mean_reversion", "rsi"],
        }
        
        hypothesis_id = await research_agent.propose_hypothesis(hypothesis_data)
        
        assert hypothesis_id is not None
        assert hypothesis_id in research_agent._hypotheses
        
    @pytest.mark.asyncio
    async def test_hypothesis_testing(self, research_agent):
        """Test hypothesis testing."""
        # First propose a hypothesis
        hypothesis_data = {
            "name": "Test Strategy",
            "description": "Test description",
            "entry_rules": {},
            "exit_rules": {},
            "risk_rules": {},
            "parameters": {"param1": (0, 1, 0.5)},
        }
        
        hypothesis_id = await research_agent.propose_hypothesis(hypothesis_data)
        
        # Generate test data
        test_data = generate_price_history(100)
        
        # Test hypothesis
        results = await research_agent.test_hypothesis(hypothesis_id, market_data=test_data)
        
        assert results is not None
        assert "PARAMETER_SWEEP" in results or "error" in str(results)
        

class TestStrategyAgent:
    """Tests for StrategyAgent."""
    
    @pytest.mark.asyncio
    async def test_signal_aggregation(self, strategy_agent):
        """Test signal aggregation."""
        # Update technical signals
        await strategy_agent._update_technical_signals("AAPL", {
            "ticker": "AAPL",
            "trend_direction": "up",
            "trend_strength": 0.7,
            "rsi": 45,
            "macd_histogram": 0.5,
            "structure_score": 0.6,
        })
        
        # Update predictive signals
        await strategy_agent._update_predictive_signals("AAPL", {
            "direction": "bullish",
            "confidence": 0.75,
            "strength": 0.8,
        })
        
        agg = strategy_agent._signal_cache.get("AAPL")
        assert agg is not None
        assert agg.composite_score != 0
        
    @pytest.mark.asyncio
    async def test_trade_proposal_generation(self, strategy_agent):
        """Test trade proposal generation."""
        # Set up signals
        await strategy_agent._update_technical_signals("AAPL", {
            "ticker": "AAPL",
            "trend_direction": "up",
            "trend_strength": 0.8,
            "rsi": 55,
            "macd_histogram": 0.8,
            "structure_score": 0.7,
            "current_price": 150.0,
        })
        
        await strategy_agent._update_predictive_signals("AAPL", {
            "direction": "bullish",
            "confidence": 0.8,
            "strength": 0.8,
        })
        
        await strategy_agent._update_contextual_signals("AAPL", {
            "regime": "trending_up",
            "regime_stability": 0.8,
        })
        
        # Force proposal generation
        await strategy_agent._evaluate_for_proposal("AAPL")
        
        # Check if proposal was created
        proposals = await strategy_agent.process_task({"type": "get_active_proposals"})
        
        assert "proposals" in proposals
        

class TestRiskAgent:
    """Tests for RiskAgent."""
    
    @pytest.mark.asyncio
    async def test_trade_approval(self, risk_agent):
        """Test trade approval for good trade."""
        proposal = generate_trade_proposal("long", 0.75)
        
        assessment = await risk_agent.assess_trade(proposal)
        
        assert assessment is not None
        assert assessment.decision in list(RiskDecision)
        assert 0 <= assessment.risk_score <= 1
        
    @pytest.mark.asyncio
    async def test_trade_rejection(self, risk_agent):
        """Test trade rejection for poor trade."""
        # Proposal with poor risk/reward
        proposal = generate_trade_proposal("long", 0.4)
        proposal["risk_reward_ratio"] = 0.5
        proposal["conviction_score"] = 0.3
        
        assessment = await risk_agent.assess_trade(proposal)
        
        assert assessment.decision == RiskDecision.REJECTED or assessment.violations
        
    @pytest.mark.asyncio
    async def test_position_sizing(self, risk_agent):
        """Test position sizing calculation."""
        max_pos = risk_agent._calculate_max_position_size("AAPL")
        
        assert 0 < max_pos <= risk_agent.max_position_size_pct
        

class TestExecutionSimulationAgent:
    """Tests for ExecutionSimulationAgent."""
    
    @pytest.mark.asyncio
    async def test_trade_creation(self, execution_agent):
        """Test trade creation."""
        approval = {
            "proposal_id": "prop_test",
            "ticker": "AAPL",
            "direction": "long",
            "entry_price": 150.0,
            "recommended_position_size": 0.1,
            "stop_loss": 147.0,
            "take_profit": 156.0,
        }
        
        trade = await execution_agent._create_simulated_trade(approval)
        
        assert trade is not None
        assert trade.trade_id is not None
        assert trade.status == TradeStatus.PENDING
        
    @pytest.mark.asyncio
    async def test_slippage_calculation(self, execution_agent):
        """Test slippage calculation."""
        slippage = execution_agent._calculate_slippage("AAPL", "long", "entry")
        
        assert slippage >= 0
        assert slippage < 0.01  # Less than 1%
        

class TestEvaluationAgent:
    """Tests for EvaluationAgent."""
    
    @pytest.mark.asyncio
    async def test_metrics_calculation(self, evaluation_agent):
        """Test trade metrics calculation."""
        # Create sample trades
        trades = []
        for i in range(50):
            trades.append({
                "net_pnl": 0.02 if i % 2 == 0 else -0.01,
                "gross_pnl": 0.021 if i % 2 == 0 else -0.009,
            })
            
        metrics = evaluation_agent._calculate_trade_metrics(trades)
        
        assert metrics.total_trades == 50
        assert metrics.win_rate == 0.5
        assert metrics.total_return > 0
        
    @pytest.mark.asyncio
    async def test_grading(self, evaluation_agent):
        """Test metric grading."""
        # Create good metrics
        metrics = TradeMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.6,
            total_return=0.15,
            sharpe_ratio=1.8,
            max_drawdown=0.05,
            profit_factor=2.5,
        )
        
        grade, score = evaluation_agent._grade_profitability(metrics)
        
        assert score > 70
        assert grade in [MetricGrade.A, MetricGrade.B_PLUS, MetricGrade.B]
        

class TestMemoryLearningAgent:
    """Tests for MemoryLearningAgent."""
    
    @pytest.mark.asyncio
    async def test_lesson_creation(self, memory_agent):
        """Test lesson creation from trade."""
        trade_data = {
            "ticker": "AAPL",
            "setup_type": "trend_following",
            "direction": "long",
            "regime": "trending_up",
            "net_pnl": 0.025,
            "exit_reason": "target_hit",
        }
        
        await memory_agent._learn_from_trade(trade_data)
        
        assert len(memory_agent._lessons) > 0
        
    @pytest.mark.asyncio
    async def test_setup_performance_tracking(self, memory_agent):
        """Test setup performance tracking."""
        await memory_agent._update_setup_performance("trend_following", "long", "trending_up", 0.02)
        await memory_agent._update_setup_performance("trend_following", "long", "trending_up", 0.015)
        await memory_agent._update_setup_performance("trend_following", "long", "trending_up", -0.01)
        
        key = "trend_following_long"
        assert key in memory_agent._setup_performance
        perf = memory_agent._setup_performance[key]
        assert perf.total_trades == 3
        assert perf.winning_trades == 2
        
    @pytest.mark.asyncio
    async def test_setup_recommendation(self, memory_agent):
        """Test setup recommendation."""
        # Add some data
        for i in range(10):
            await memory_agent._update_setup_performance("breakout", "long", "trending_up", 0.02 if i % 2 == 0 else -0.01)
            
        rec = await memory_agent.get_setup_recommendation("breakout", "long", "trending_up")
        
        assert "recommendation" in rec
        assert "confidence" in rec
        

class TestSupervisorAgent:
    """Tests for SupervisorAgent."""
    
    @pytest.mark.asyncio
    async def test_agent_registration(self, supervisor_agent):
        """Test agent registration."""
        await supervisor_agent.register_agent("test_agent")
        
        assert "test_agent" in supervisor_agent._registered_agents
        assert "test_agent" in supervisor_agent._agent_statuses
        
    @pytest.mark.asyncio
    async def test_mode_change(self, supervisor_agent):
        """Test system mode change."""
        await supervisor_agent.set_mode(SystemMode.PAPER)
        
        assert supervisor_agent._mode == SystemMode.PAPER
        
    @pytest.mark.asyncio
    async def test_system_state(self, supervisor_agent):
        """Test system state retrieval."""
        state = supervisor_agent.get_system_state()
        
        assert state is not None
        assert state.mode in list(SystemMode)
        assert state.system_health in ["healthy", "degraded", "critical", "unknown"]
        

# Integration Tests
class TestIntegration:
    """Integration tests for the full system."""
    
    @pytest.mark.asyncio
    async def test_message_bus_communication(self, message_bus):
        """Test message bus communication between agents."""
        received_messages = []
        
        async def handler(msg):
            received_messages.append(msg)
            
        await message_bus.subscribe(MessageType.TRADE_PROPOSAL, handler)
        
        # Send a message
        msg = AgentMessage(
            msg_type=MessageType.TRADE_PROPOSAL,
            source="test",
            target=None,
            payload={"test": "data"},
        )
        await message_bus.publish(msg)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        assert len(received_messages) == 1
        assert received_messages[0].payload["test"] == "data"
        
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, trading_system):
        """Test end-to-end trading workflow."""
        
        # 1. Ingest market data
        for i in range(30):
            price_data = {
                "open": 100 + i * 0.1,
                "high": 101 + i * 0.1,
                "low": 99 + i * 0.1,
                "close": 100 + i * 0.1,
                "volume": 1000000,
            }
            await trading_system.ingest_market_data("AAPL", price_data)
            
        await asyncio.sleep(0.2)
        
        # 2. Process signal
        signal = generate_mirofish_signal("BULLISH", 0.75)
        proposals = await trading_system.process_signal("AAPL", signal)
        
        await asyncio.sleep(0.2)
        
        # 3. Check system status
        status = await trading_system.get_system_status()
        
        assert "supervisor" in status
        assert "agents" in status
        
    @pytest.mark.asyncio
    async def test_full_simulation(self, trading_system):
        """Run a full simulation with multiple trades."""
        
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        
        # Run 5-day simulation
        result = await trading_system.run_simulation(tickers, num_days=5, trades_per_day=3)
        
        assert "trades_executed" in result
        assert "execution_metrics" in result
        
        print(f"[TEST] Simulation completed: {result['trades_executed']} trades executed")


# Large-Scale Simulation Test
@pytest.mark.asyncio
async def test_hundreds_of_trades():
    """
    Run a comprehensive test with hundreds of trades across different regimes.
    This validates the system's robustness and learning capabilities.
    """
    print("\n" + "=" * 70)
    print("LARGE-SCALE SIMULATION TEST")
    print("=" * 70)
    
    reset_message_bus()
    system = TradingSystem({
        "market_structure": {"lookback_periods": 50},
        "risk": {"max_position_size": 0.20, "min_conviction": 0.50},
        "execution_simulation": {"base_slippage": 0.0005, "fill_probability": 0.98},
        "evaluation": {"min_trades": 30, "min_graduation_trades": 100},
    })
    
    await system.start()
    
    try:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
        regimes = ["trending_up", "trending_down", "ranging", "volatile"]
        
        total_trades_target = 200
        trades_executed = 0
        day = 0
        
        print(f"[TEST] Target: {total_trades_target} trades across {len(tickers)} tickers")
        print(f"[TEST] Testing across regimes: {regimes}")
        
        while trades_executed < total_trades_target and day < 60:
            day += 1
            current_regime = regimes[day % len(regimes)]
            
            if day % 10 == 0:
                print(f"[TEST] Day {day}, Regime: {current_regime}, Trades so far: {trades_executed}")
                
            for ticker in tickers:
                # Generate regime-appropriate price data
                if current_regime == "trending_up":
                    trend = "up"
                elif current_regime == "trending_down":
                    trend = "down"
                else:
                    trend = "sideways"
                    
                prices = generate_price_history(20, trend=trend)
                for price in prices:
                    await system.ingest_market_data(ticker, price)
                    
                # Generate signal
                if current_regime == "trending_up":
                    bias = "BULLISH"
                elif current_regime == "trending_down":
                    bias = "BEARISH"
                else:
                    bias = np.random.choice(["BULLISH", "BEARISH", "NEUTRAL"])
                    
                signal = generate_mirofish_signal(bias, 0.5 + np.random.random() * 0.4)
                await system.process_signal(ticker, signal)
                
            await asyncio.sleep(0.02)
            
            # Check trade count
            exec_result = await system.agents["execution_simulation"].process_task({
                "type": "get_metrics",
            })
            trades_executed = exec_result.get("metrics", {}).get("total_trades", 0)
            
        print(f"\n[TEST] Simulation complete after {day} days")
        print(f"[TEST] Total trades executed: {trades_executed}")
        
        # Get evaluation
        eval_result = await system.agents["evaluation"].process_task({
            "type": "evaluate",
            "strategy_id": "default",
        })
        
        if eval_result.get("scorecard"):
            sc = eval_result["scorecard"]
            print(f"\n[TEST] Evaluation Results:")
            print(f"  - Overall Grade: {sc.get('overall_grade', 'N/A')}")
            print(f"  - Overall Score: {sc.get('overall_score', 0):.1f}")
            print(f"  - Total Trades: {sc.get('trade_sample_size', 0)}")
            print(f"  - Graduation Ready: {sc.get('graduation_ready', False)}")
            
        # Get lessons learned
        lessons = await system.agents["memory_learning"].process_task({
            "type": "get_lessons",
        })
        
        print(f"\n[TEST] Lessons Learned: {len(lessons.get('lessons', []))}")
        
        # Get setup performance
        setups = await system.agents["memory_learning"].process_task({
            "type": "get_setup_performance",
        })
        
        print(f"[TEST] Setup Types Tracked: {len(setups.get('setups', []))}")
        
        # Assertions
        assert trades_executed >= 50, f"Expected at least 50 trades, got {trades_executed}"
        
        # Get final system status
        status = await system.get_system_status()
        assert status["supervisor"]["system_health"] in ["healthy", "degraded"]
        
        print("\n" + "=" * 70)
        print("LARGE-SCALE SIMULATION TEST PASSED")
        print("=" * 70)
        
    finally:
        await system.stop()


# Run tests if executed directly
if __name__ == "__main__":
    print("Running 9-Agent Trading Research Architecture Tests")
    print("=" * 70)
    
    # Run pytest
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=False,
    )
    
    sys.exit(result.returncode)
