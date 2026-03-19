#!/usr/bin/env python3
"""
Demo script for the 9-Agent Trading Research Architecture.

This script demonstrates how to use the trading system for:
1. Running a research cycle
2. Processing market signals
3. Evaluating performance
4. Learning from results
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents import TradingSystem, reset_message_bus


async def demo_research_cycle():
    """Demonstrate a research cycle."""
    print("\n" + "=" * 70)
    print("DEMO: Research Cycle")
    print("=" * 70)
    
    reset_message_bus()
    system = TradingSystem()
    await system.start()
    
    try:
        # Propose a hypothesis
        hypothesis = {
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
        
        print("\n[1] Proposing hypothesis...")
        result = await system.run_research_cycle(hypothesis)
        print(f"    Hypothesis ID: {result.get('hypothesis_id')}")
        
        # Get research results
        print("\n[2] Research results:")
        test_result = result.get('test_result', {})
        if 'PARAMETER_SWEEP' in test_result:
            print("    - Parameter sweep completed")
        if 'REGIME_ROBUSTNESS' in test_result:
            print("    - Regime robustness test completed")
            
    finally:
        await system.stop()


async def demo_signal_processing():
    """Demonstrate signal processing workflow."""
    print("\n" + "=" * 70)
    print("DEMO: Signal Processing")
    print("=" * 70)
    
    reset_message_bus()
    system = TradingSystem()
    await system.start()
    
    try:
        # Ingest market data
        print("\n[1] Ingesting market data...")
        for i in range(30):
            price_data = {
                "open": 100 + i * 0.1,
                "high": 101 + i * 0.1,
                "low": 99 + i * 0.1,
                "close": 100 + i * 0.1,
                "volume": 1000000,
            }
            await system.ingest_market_data("AAPL", price_data)
        print("    Ingested 30 price bars")
        
        # Process MiroFish signal
        print("\n[2] Processing MiroFish signal...")
        signal = {
            "directional_bias": "BULLISH",
            "confidence": 0.75,
            "scenario_summary": "Bullish breakout expected",
            "catalyst_summary": "Strong earnings momentum",
            "risk_flags": [],
            "scenarios": [
                {"probability": 0.75, "direction": "BULLISH"},
                {"probability": 0.15, "direction": "NEUTRAL"},
                {"probability": 0.10, "direction": "BEARISH"},
            ],
            "model_votes": {
                "bullish": 6,
                "bearish": 2,
                "neutral": 2,
            },
        }
        
        proposals = await system.process_signal("AAPL", signal)
        print(f"    Active proposals: {len(proposals.get('proposals', []))}")
        
        # Get system status
        print("\n[3] System status:")
        status = await system.get_system_status()
        print(f"    - System mode: {status['supervisor'].get('system_mode', 'unknown')}")
        print(f"    - Registered agents: {status['supervisor'].get('agent_count', 0)}")
        print(f"    - System health: {status['supervisor'].get('system_health', 'unknown')}")
        
    finally:
        await system.stop()


async def demo_simulation():
    """Demonstrate full simulation."""
    print("\n" + "=" * 70)
    print("DEMO: Full Simulation")
    print("=" * 70)
    
    reset_message_bus()
    system = TradingSystem({
        "market_structure": {"lookback_periods": 50},
        "risk": {"max_position_size": 0.20, "min_conviction": 0.50},
        "execution_simulation": {"base_slippage": 0.0005},
        "evaluation": {"min_trades": 30, "min_graduation_trades": 50},
    })
    
    await system.start()
    
    try:
        tickers = ["AAPL", "MSFT", "GOOGL"]
        
        print(f"\n[1] Running 10-day simulation on {len(tickers)} tickers...")
        result = await system.run_simulation(tickers, num_days=10, trades_per_day=2)
        
        print(f"\n[2] Simulation Results:")
        print(f"    - Days simulated: {result['simulation_days']}")
        print(f"    - Trades executed: {result['trades_executed']}")
        
        metrics = result.get('execution_metrics', {})
        print(f"    - Win rate: {metrics.get('win_rate', 0):.1%}")
        print(f"    - Total PnL: {metrics.get('total_net_pnl', 0):.2%}")
        
        # Get evaluation
        print("\n[3] Evaluation report:")
        eval_report = await system.get_evaluation_report("default")
        scorecard = eval_report.get('scorecard', {})
        
        if scorecard:
            print(f"    - Overall grade: {scorecard.get('overall_grade', 'N/A')}")
            print(f"    - Overall score: {scorecard.get('overall_score', 0):.1f}")
            print(f"    - Graduation ready: {scorecard.get('graduation_ready', False)}")
        else:
            print("    - Insufficient trades for evaluation")
            
        # Get lessons learned
        print("\n[4] Lessons learned:")
        lessons = await system.get_lessons_learned()
        lesson_list = lessons.get('lessons', [])
        print(f"    - Total lessons: {len(lesson_list)}")
        
        for lesson in lesson_list[:3]:
            print(f"      * {lesson.get('type', 'unknown')}: {lesson.get('description', '')[:50]}...")
            
    finally:
        await system.stop()


async def demo_multi_regime():
    """Demonstrate trading across multiple market regimes."""
    print("\n" + "=" * 70)
    print("DEMO: Multi-Regime Trading")
    print("=" * 70)
    
    reset_message_bus()
    system = TradingSystem()
    await system.start()
    
    try:
        tickers = ["AAPL", "TSLA", "NVDA"]
        regimes = ["trending_up", "trending_down", "ranging", "volatile"]
        
        print(f"\n[1] Testing across {len(regimes)} market regimes...")
        
        for day, regime in enumerate(regimes):
            print(f"\n    Day {day + 1}: {regime}")
            
            for ticker in tickers:
                # Generate regime-appropriate data
                import numpy as np
                
                if regime == "trending_up":
                    trend = "up"
                    bias = "BULLISH"
                elif regime == "trending_down":
                    trend = "down"
                    bias = "BEARISH"
                else:
                    trend = "sideways"
                    bias = np.random.choice(["BULLISH", "BEARISH"])
                    
                # Generate and ingest prices
                for i in range(20):
                    base = 100
                    if trend == "up":
                        close = base + i * 0.2 + np.random.normal(0, 0.5)
                    elif trend == "down":
                        close = base - i * 0.2 + np.random.normal(0, 0.5)
                    else:
                        close = base + np.random.normal(0, 1)
                        
                    price_data = {
                        "open": close - 0.5,
                        "high": close + 1,
                        "low": close - 1,
                        "close": close,
                        "volume": 1000000,
                    }
                    await system.ingest_market_data(ticker, price_data)
                    
                # Generate signal
                signal = {
                    "directional_bias": bias,
                    "confidence": 0.6 + np.random.random() * 0.3,
                    "scenario_summary": f"{bias} in {regime}",
                    "catalyst_summary": "Test catalyst",
                    "risk_flags": [],
                    "scenarios": [
                        {"probability": 0.7, "direction": bias},
                        {"probability": 0.3, "direction": "NEUTRAL"},
                    ],
                    "model_votes": {
                        "bullish": 5 if bias == "BULLISH" else 2,
                        "bearish": 5 if bias == "BEARISH" else 2,
                        "neutral": 1,
                    },
                }
                
                await system.process_signal(ticker, signal)
                
            await asyncio.sleep(0.05)
            
        # Get regime-specific performance
        print("\n[2] Checking regime pattern memory...")
        regime_patterns = await system.agents["memory_learning"].process_task({
            "type": "get_regime_patterns",
        })
        
        patterns = regime_patterns.get('patterns', [])
        print(f"    - Patterns learned: {len(patterns)}")
        
        for pattern in patterns[:3]:
            print(f"      * {pattern.get('regime')}/{pattern.get('pattern_type')}: "
                  f"{pattern.get('success_rate', 0):.1%} win rate")
                  
    finally:
        await system.stop()


async def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("9-AGENT TRADING RESEARCH ARCHITECTURE - DEMO")
    print("=" * 70)
    print("\nThis demo showcases the complete 9-agent trading research system.")
    print("Each agent has a specific role in the hypothesis-driven workflow.")
    
    await demo_research_cycle()
    await demo_signal_processing()
    await demo_simulation()
    await demo_multi_regime()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("\nThe 9-Agent Trading Research Architecture includes:")
    print("  1. MarketStructureAgent    - Analyzes price action & regimes")
    print("  2. MiroFishSignalAgent     - Ingests predictive signals")
    print("  3. ResearchAgent           - Tests hypotheses systematically")
    print("  4. StrategyAgent           - Combines signals into trade ideas")
    print("  5. RiskAgent               - Validates and approves trades")
    print("  6. ExecutionSimulationAgent- Paper trades approved setups")
    print("  7. EvaluationAgent         - Studies results for robustness")
    print("  8. MemoryLearningAgent     - Stores lessons & updates beliefs")
    print("  9. SupervisorAgent         - Orchestrates all agents")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
