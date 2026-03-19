"""
Research Agent

Tests strategy hypotheses systematically.
Explores rule sets and parameter combinations.
Compares setups across different market periods.

Outputs:
- Strategy variants
- Performance summaries
- Failure modes
"""

from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
import itertools
import numpy as np
from collections import defaultdict

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class HypothesisStatus(Enum):
    """Status of a hypothesis."""
    PROPOSED = auto()
    TESTING = auto()
    VALIDATED = auto()
    REJECTED = auto()
    INCONCLUSIVE = auto()


class TestType(Enum):
    """Types of tests that can be run."""
    PARAMETER_SWEEP = auto()
    REGIME_ROBUSTNESS = auto()
    TIME_PERIOD = auto()
    MONTE_CARLO = auto()
    WALK_FORWARD = auto()
    STRESS_TEST = auto()


@dataclass
class Hypothesis:
    """A trading hypothesis to test."""
    hypothesis_id: str
    name: str
    description: str
    
    # Strategy definition
    entry_rules: Dict[str, Any]
    exit_rules: Dict[str, Any]
    risk_rules: Dict[str, Any]
    
    # Test parameters
    parameters: Dict[str, Tuple[float, float, float]]  # name -> (min, max, step)
    
    # Status
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    created_at: datetime = field(default_factory=datetime.utcnow)
    tested_at: Optional[datetime] = None
    
    # Results
    test_results: List[Dict] = field(default_factory=list)
    best_variant: Optional[Dict] = None
    failure_modes: List[Dict] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    priority: int = 5  # 1 = highest


@dataclass
class StrategyVariant:
    """A specific parameter combination of a hypothesis."""
    variant_id: str
    hypothesis_id: str
    parameters: Dict[str, float]
    
    # Performance metrics
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    num_trades: int = 0
    
    # Robustness metrics
    regime_performance: Dict[str, float] = field(default_factory=dict)
    period_consistency: float = 0.0
    param_sensitivity: float = 0.0
    
    # Overall score
    fitness_score: float = 0.0
    robustness_score: float = 0.0


@dataclass
class TestResult:
    """Results from a single test run."""
    test_id: str
    test_type: TestType
    hypothesis_id: str
    variant_id: Optional[str]
    
    # Period tested
    start_date: datetime
    end_date: datetime
    regime_filter: Optional[str]
    
    # Performance
    metrics: Dict[str, float]
    trades: List[Dict]
    equity_curve: List[float]
    
    # Analysis
    strengths: List[str]
    weaknesses: List[str]
    anomalies: List[str]
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ResearchAgent(BaseAgent):
    """
    Agent for systematic strategy research and hypothesis testing.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("research", message_bus, config)
        
        # Configuration
        self.max_variants_per_hypothesis = config.get("max_variants", 100) if config else 100
        self.min_trades_for_validity = config.get("min_trades", 30) if config else 30
        self.significance_threshold = config.get("significance", 0.05) if config else 0.05
        
        # State
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._variants: Dict[str, StrategyVariant] = {}
        self._test_results: List[TestResult] = []
        
        # Test functions registry
        self._test_functions: Dict[TestType, Callable] = {
            TestType.PARAMETER_SWEEP: self._run_parameter_sweep,
            TestType.REGIME_ROBUSTNESS: self._run_regime_robustness,
            TestType.TIME_PERIOD: self._run_time_period_test,
            TestType.MONTE_CARLO: self._run_monte_carlo,
            TestType.WALK_FORWARD: self._run_walk_forward,
        }
        
        # Market data cache
        self._market_data: Dict[str, List[Dict]] = {}
        
    async def propose_hypothesis(self, hypothesis_data: Dict[str, Any]) -> str:
        """Propose a new hypothesis for testing."""
        hypothesis_id = f"hyp_{datetime.utcnow().timestamp()}"
        
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            name=hypothesis_data.get("name", "Unnamed"),
            description=hypothesis_data.get("description", ""),
            entry_rules=hypothesis_data.get("entry_rules", {}),
            exit_rules=hypothesis_data.get("exit_rules", {}),
            risk_rules=hypothesis_data.get("risk_rules", {}),
            parameters=hypothesis_data.get("parameters", {}),
            tags=hypothesis_data.get("tags", []),
            priority=hypothesis_data.get("priority", 5),
        )
        
        self._hypotheses[hypothesis_id] = hypothesis
        
        # Publish hypothesis proposed
        await self.send_message(
            MessageType.HYPOTHESIS_PROPOSED,
            {
                "hypothesis_id": hypothesis_id,
                "name": hypothesis.name,
                "description": hypothesis.description,
                "tags": hypothesis.tags,
                "priority": hypothesis.priority,
            }
        )
        
        return hypothesis_id
        
    async def test_hypothesis(
        self, 
        hypothesis_id: str,
        test_types: Optional[List[TestType]] = None,
        market_data: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive tests on a hypothesis."""
        hypothesis = self._hypotheses.get(hypothesis_id)
        if not hypothesis:
            return {"error": f"Hypothesis {hypothesis_id} not found"}
            
        hypothesis.status = HypothesisStatus.TESTING
        
        # Use provided data or fetch
        data = market_data or self._market_data.get(hypothesis.tags[0] if hypothesis.tags else "default", [])
        
        if not data:
            return {"error": "No market data available for testing"}
            
        # Default test suite
        test_types = test_types or [
            TestType.PARAMETER_SWEEP,
            TestType.REGIME_ROBUSTNESS,
            TestType.WALK_FORWARD,
        ]
        
        results = {}
        
        for test_type in test_types:
            try:
                test_fn = self._test_functions.get(test_type)
                if test_fn:
                    result = await test_fn(hypothesis, data)
                    results[test_type.name] = result
                    
                    if isinstance(result, TestResult):
                        self._test_results.append(result)
                        hypothesis.test_results.append({
                            "test_id": result.test_id,
                            "test_type": test_type.name,
                            "metrics": result.metrics,
                        })
            except Exception as e:
                results[test_type.name] = {"error": str(e)}
                
        # Analyze results
        await self._analyze_hypothesis_results(hypothesis, results)
        
        # Publish results
        await self.send_message(
            MessageType.HYPOTHESIS_TESTED,
            {
                "hypothesis_id": hypothesis_id,
                "status": hypothesis.status.name,
                "best_variant": hypothesis.best_variant,
                "failure_modes": hypothesis.failure_modes,
            }
        )
        
        return results
        
    async def _run_parameter_sweep(
        self, 
        hypothesis: Hypothesis, 
        data: List[Dict]
    ) -> TestResult:
        """Run parameter sweep to find optimal settings."""
        
        # Generate parameter combinations
        param_ranges = []
        param_names = []
        
        for name, (min_val, max_val, step) in hypothesis.parameters.items():
            param_names.append(name)
            values = np.arange(min_val, max_val + step, step)
            param_ranges.append(values)
            
        # Limit combinations
        combinations = list(itertools.product(*param_ranges))
        if len(combinations) > self.max_variants_per_hypothesis:
            # Sample evenly
            indices = np.linspace(0, len(combinations) - 1, self.max_variants_per_hypothesis, dtype=int)
            combinations = [combinations[i] for i in indices]
            
        variants = []
        
        for combo in combinations:
            params = dict(zip(param_names, combo))
            variant_id = f"var_{hypothesis.hypothesis_id}_{len(variants)}"
            
            variant = StrategyVariant(
                variant_id=variant_id,
                hypothesis_id=hypothesis.hypothesis_id,
                parameters=params,
            )
            
            # Simulate with these parameters
            metrics = await self._simulate_strategy(hypothesis, params, data)
            
            variant.total_return = metrics.get("total_return", 0)
            variant.sharpe_ratio = metrics.get("sharpe_ratio", 0)
            variant.max_drawdown = metrics.get("max_drawdown", 0)
            variant.win_rate = metrics.get("win_rate", 0)
            variant.profit_factor = metrics.get("profit_factor", 0)
            variant.num_trades = metrics.get("num_trades", 0)
            
            # Calculate fitness
            variant.fitness_score = self._calculate_fitness(variant)
            
            self._variants[variant_id] = variant
            variants.append(variant)
            
        # Find best variant
        if variants:
            best = max(variants, key=lambda v: v.fitness_score)
            hypothesis.best_variant = {
                "variant_id": best.variant_id,
                "parameters": best.parameters,
                "fitness_score": best.fitness_score,
                "metrics": {
                    "total_return": best.total_return,
                    "sharpe_ratio": best.sharpe_ratio,
                    "max_drawdown": best.max_drawdown,
                    "win_rate": best.win_rate,
                }
            }
            
        return TestResult(
            test_id=f"test_param_sweep_{datetime.utcnow().timestamp()}",
            test_type=TestType.PARAMETER_SWEEP,
            hypothesis_id=hypothesis.hypothesis_id,
            variant_id=None,
            start_date=datetime.utcnow() - timedelta(days=365),
            end_date=datetime.utcnow(),
            regime_filter=None,
            metrics={
                "variants_tested": len(variants),
                "best_fitness": hypothesis.best_variant["fitness_score"] if hypothesis.best_variant else 0,
            },
            trades=[],
            equity_curve=[],
            strengths=["Comprehensive parameter exploration"],
            weaknesses=["Computationally expensive"] if len(variants) > 50 else [],
            anomalies=[],
        )
        
    async def _run_regime_robustness(
        self, 
        hypothesis: Hypothesis, 
        data: List[Dict]
    ) -> TestResult:
        """Test strategy across different market regimes."""
        
        # Split data by regime
        regime_data = defaultdict(list)
        for bar in data:
            regime = bar.get("regime", "unknown")
            regime_data[regime].append(bar)
            
        if not hypothesis.best_variant:
            # Use default parameters
            params = {name: (min_val + max_val) / 2 for name, (min_val, max_val, _) in hypothesis.parameters.items()}
        else:
            params = hypothesis.best_variant["parameters"]
            
        regime_performance = {}
        all_trades = []
        
        for regime, regime_bars in regime_data.items():
            if len(regime_bars) < 20:
                continue
                
            metrics = await self._simulate_strategy(hypothesis, params, regime_bars)
            regime_performance[regime] = metrics.get("total_return", 0)
            all_trades.extend(metrics.get("trades", []))
            
        # Calculate consistency
        returns = list(regime_performance.values())
        consistency = 1 - (np.std(returns) / abs(np.mean(returns))) if returns and np.mean(returns) != 0 else 0
        
        # Update best variant
        if hypothesis.best_variant:
            variant_id = hypothesis.best_variant["variant_id"]
            variant = self._variants.get(variant_id)
            if variant:
                variant.regime_performance = regime_performance
                variant.period_consistency = consistency
                
        # Identify failure modes
        for regime, ret in regime_performance.items():
            if ret < -0.1:  # Lost more than 10%
                hypothesis.failure_modes.append({
                    "type": "regime_failure",
                    "regime": regime,
                    "return": ret,
                    "description": f"Strategy performs poorly in {regime} regime",
                })
                
        return TestResult(
            test_id=f"test_regime_{datetime.utcnow().timestamp()}",
            test_type=TestType.REGIME_ROBUSTNESS,
            hypothesis_id=hypothesis.hypothesis_id,
            variant_id=hypothesis.best_variant["variant_id"] if hypothesis.best_variant else None,
            start_date=datetime.utcnow() - timedelta(days=365),
            end_date=datetime.utcnow(),
            regime_filter=None,
            metrics={
                "regime_performance": regime_performance,
                "consistency_score": consistency,
                "num_regimes_tested": len(regime_performance),
            },
            trades=all_trades,
            equity_curve=[],
            strengths=["Tests robustness across market conditions"],
            weaknesses=[],
            anomalies=[],
        )
        
    async def _run_time_period_test(
        self, 
        hypothesis: Hypothesis, 
        data: List[Dict]
    ) -> TestResult:
        """Test strategy across different time periods."""
        
        # Split data into periods
        period_size = len(data) // 4
        periods = [
            data[i:i+period_size] for i in range(0, len(data), period_size)
        ]
        
        if not hypothesis.best_variant:
            params = {name: (min_val + max_val) / 2 for name, (min_val, max_val, _) in hypothesis.parameters.items()}
        else:
            params = hypothesis.best_variant["parameters"]
            
        period_returns = []
        
        for i, period_data in enumerate(periods):
            if len(period_data) < 20:
                continue
                
            metrics = await self._simulate_strategy(hypothesis, params, period_data)
            period_returns.append(metrics.get("total_return", 0))
            
        # Calculate consistency
        consistency = 1 - (np.std(period_returns) / abs(np.mean(period_returns))) if period_returns and np.mean(period_returns) != 0 else 0
        
        return TestResult(
            test_id=f"test_period_{datetime.utcnow().timestamp()}",
            test_type=TestType.TIME_PERIOD,
            hypothesis_id=hypothesis.hypothesis_id,
            variant_id=hypothesis.best_variant["variant_id"] if hypothesis.best_variant else None,
            start_date=datetime.utcnow() - timedelta(days=365),
            end_date=datetime.utcnow(),
            regime_filter=None,
            metrics={
                "period_returns": period_returns,
                "consistency_score": consistency,
            },
            trades=[],
            equity_curve=[],
            strengths=["Tests temporal stability"],
            weaknesses=[],
            anomalies=[],
        )
        
    async def _run_monte_carlo(
        self, 
        hypothesis: Hypothesis, 
        data: List[Dict]
    ) -> TestResult:
        """Run Monte Carlo simulation."""
        
        if not hypothesis.best_variant:
            return TestResult(
                test_id=f"test_mc_{datetime.utcnow().timestamp()}",
                test_type=TestType.MONTE_CARLO,
                hypothesis_id=hypothesis.hypothesis_id,
                variant_id=None,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow(),
                regime_filter=None,
                metrics={"error": "No best variant for Monte Carlo"},
                trades=[],
                equity_curve=[],
                strengths=[],
                weaknesses=["Requires validated strategy"],
                anomalies=[],
            )
            
        params = hypothesis.best_variant["parameters"]
        
        # Run multiple simulations with shuffled data
        simulations = []
        for _ in range(100):
            shuffled = data.copy()
            np.random.shuffle(shuffled)
            metrics = await self._simulate_strategy(hypothesis, params, shuffled)
            simulations.append(metrics.get("total_return", 0))
            
        # Calculate statistics
        mc_mean = np.mean(simulations)
        mc_std = np.std(simulations)
        mc_var_95 = np.percentile(simulations, 5)
        
        return TestResult(
            test_id=f"test_mc_{datetime.utcnow().timestamp()}",
            test_type=TestType.MONTE_CARLO,
            hypothesis_id=hypothesis.hypothesis_id,
            variant_id=hypothesis.best_variant["variant_id"],
            start_date=datetime.utcnow() - timedelta(days=365),
            end_date=datetime.utcnow(),
            regime_filter=None,
            metrics={
                "mc_mean_return": mc_mean,
                "mc_std": mc_std,
                "mc_var_95": mc_var_95,
                "mc_median": np.median(simulations),
            },
            trades=[],
            equity_curve=[],
            strengths=["Tests statistical significance"],
            weaknesses=["Assumes returns are independent"],
            anomalies=[],
        )
        
    async def _run_walk_forward(
        self, 
        hypothesis: Hypothesis, 
        data: List[Dict]
    ) -> TestResult:
        """Run walk-forward optimization."""
        
        window_size = len(data) // 5
        results = []
        
        for i in range(0, len(data) - window_size * 2, window_size):
            # In-sample optimization
            in_sample = data[i:i+window_size]
            out_sample = data[i+window_size:i+window_size*2]
            
            # Find best params on in-sample
            best_params = await self._optimize_params(hypothesis, in_sample)
            
            # Test on out-of-sample
            metrics = await self._simulate_strategy(hypothesis, best_params, out_sample)
            results.append(metrics.get("total_return", 0))
            
        # Calculate walk-forward efficiency
        wf_efficiency = np.mean(results) if results else 0
        
        return TestResult(
            test_id=f"test_wf_{datetime.utcnow().timestamp()}",
            test_type=TestType.WALK_FORWARD,
            hypothesis_id=hypothesis.hypothesis_id,
            variant_id=hypothesis.best_variant["variant_id"] if hypothesis.best_variant else None,
            start_date=datetime.utcnow() - timedelta(days=365),
            end_date=datetime.utcnow(),
            regime_filter=None,
            metrics={
                "walk_forward_efficiency": wf_efficiency,
                "out_of_sample_returns": results,
                "wf_consistency": 1 - (np.std(results) / abs(np.mean(results))) if results and np.mean(results) != 0 else 0,
            },
            trades=[],
            equity_curve=[],
            strengths=["Tests out-of-sample performance"],
            weaknesses=["Sensitive to window size"],
            anomalies=[],
        )
        
    async def _simulate_strategy(
        self, 
        hypothesis: Hypothesis, 
        params: Dict[str, float], 
        data: List[Dict]
    ) -> Dict[str, Any]:
        """Simulate strategy performance."""
        
        trades = []
        equity = [10000.0]  # Start with $10k
        position = 0
        entry_price = 0
        
        for i, bar in enumerate(data):
            close = bar.get("close", 0)
            
            # Check entry
            if position == 0:
                should_enter = self._check_entry(hypothesis.entry_rules, bar, params)
                if should_enter:
                    position = 1
                    entry_price = close
                    
            # Check exit
            elif position == 1:
                should_exit = self._check_exit(hypothesis.exit_rules, bar, params, entry_price)
                if should_exit:
                    pnl = (close - entry_price) / entry_price if entry_price > 0 else 0
                    trades.append({
                        "entry": entry_price,
                        "exit": close,
                        "pnl": pnl,
                    })
                    equity.append(equity[-1] * (1 + pnl))
                    position = 0
                    
        # Calculate metrics
        if len(trades) < self.min_trades_for_validity:
            return {
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "num_trades": len(trades),
                "trades": trades,
            }
            
        returns = [t["pnl"] for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        
        total_return = (equity[-1] - equity[0]) / equity[0]
        win_rate = len(wins) / len(trades) if trades else 0
        
        # Sharpe (simplified)
        sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        
        # Max drawdown
        peak = equity[0]
        max_dd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak
            max_dd = max(max_dd, dd)
            
        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "num_trades": len(trades),
            "trades": trades,
        }
        
    def _check_entry(self, rules: Dict, bar: Dict, params: Dict) -> bool:
        """Check if entry conditions are met."""
        # Simplified entry logic
        rsi_threshold = params.get("rsi_entry", 30)
        rsi = bar.get("rsi", 50)
        return rsi < rsi_threshold
        
    def _check_exit(self, rules: Dict, bar: Dict, params: Dict, entry_price: float) -> bool:
        """Check if exit conditions are met."""
        # Simplified exit logic
        profit_target = params.get("profit_target", 0.05)
        stop_loss = params.get("stop_loss", 0.02)
        
        close = bar.get("close", 0)
        pnl = (close - entry_price) / entry_price if entry_price > 0 else 0
        
        return pnl >= profit_target or pnl <= -stop_loss
        
    async def _optimize_params(self, hypothesis: Hypothesis, data: List[Dict]) -> Dict[str, float]:
        """Quick parameter optimization."""
        best_params = {}
        best_score = -float('inf')
        
        # Simple grid search
        for name, (min_val, max_val, step) in hypothesis.parameters.items():
            values = np.arange(min_val, max_val + step, step)
            for val in values[:5]:  # Limit for speed
                params = {name: val}
                metrics = await self._simulate_strategy(hypothesis, params, data)
                score = metrics.get("total_return", 0)
                if score > best_score:
                    best_score = score
                    best_params = params
                    
        return best_params
        
    def _calculate_fitness(self, variant: StrategyVariant) -> float:
        """Calculate overall fitness score for a variant."""
        # Multi-objective fitness
        return (
            variant.total_return * 0.3 +
            variant.sharpe_ratio * 0.2 +
            (1 - variant.max_drawdown) * 0.2 +
            variant.win_rate * 0.1 +
            min(variant.profit_factor, 3) / 3 * 0.2
        )
        
    async def _analyze_hypothesis_results(self, hypothesis: Hypothesis, results: Dict):
        """Analyze test results and update hypothesis status."""
        
        # Check if we have enough evidence
        if not hypothesis.best_variant:
            hypothesis.status = HypothesisStatus.INCONCLUSIVE
            return
            
        # Check for overfitting
        param_sweep = results.get(TestType.PARAMETER_SWEEP.name, {})
        if isinstance(param_sweep, TestResult):
            variants_tested = param_sweep.metrics.get("variants_tested", 0)
            if variants_tested > 50 and hypothesis.best_variant["fitness_score"] < 0.3:
                hypothesis.failure_modes.append({
                    "type": "overfitting",
                    "description": "Many variants tested but low fitness suggests overfitting",
                })
                
        # Check regime robustness
        regime_test = results.get(TestType.REGIME_ROBUSTNESS.name, {})
        if isinstance(regime_test, TestResult):
            consistency = regime_test.metrics.get("consistency_score", 0)
            if consistency < 0.3:
                hypothesis.failure_modes.append({
                    "type": "regime_dependency",
                    "description": f"Low regime consistency ({consistency:.2f})",
                })
                
        # Determine final status
        if hypothesis.failure_modes:
            hypothesis.status = HypothesisStatus.REJECTED
        elif hypothesis.best_variant["fitness_score"] > 0.7:
            hypothesis.status = HypothesisStatus.VALIDATED
        else:
            hypothesis.status = HypothesisStatus.INCONCLUSIVE
            
        hypothesis.tested_at = datetime.utcnow()
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        
        if task_type == "propose":
            hypothesis_id = await self.propose_hypothesis(task.get("hypothesis", {}))
            return {"hypothesis_id": hypothesis_id, "status": "proposed"}
            
        elif task_type == "test":
            hypothesis_id = task.get("hypothesis_id")
            test_types = [TestType[t] for t in task.get("test_types", [])] if task.get("test_types") else None
            results = await self.test_hypothesis(hypothesis_id, test_types)
            return {"hypothesis_id": hypothesis_id, "results": results}
            
        elif task_type == "get_hypothesis":
            hypothesis_id = task.get("hypothesis_id")
            hypothesis = self._hypotheses.get(hypothesis_id)
            return {"hypothesis": self._hypothesis_to_dict(hypothesis) if hypothesis else None}
            
        elif task_type == "list_hypotheses":
            return {
                "hypotheses": [
                    self._hypothesis_to_dict(h) for h in self._hypotheses.values()
                ]
            }
            
        elif task_type == "get_results":
            hypothesis_id = task.get("hypothesis_id")
            results = [r for r in self._test_results if r.hypothesis_id == hypothesis_id]
            return {
                "hypothesis_id": hypothesis_id,
                "test_count": len(results),
                "tests": [
                    {
                        "test_id": r.test_id,
                        "test_type": r.test_type.name,
                        "metrics": r.metrics,
                        "strengths": r.strengths,
                        "weaknesses": r.weaknesses,
                    }
                    for r in results
                ]
            }
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _hypothesis_to_dict(self, hypothesis: Hypothesis) -> Dict[str, Any]:
        """Convert hypothesis to dictionary."""
        if not hypothesis:
            return None
        return {
            "hypothesis_id": hypothesis.hypothesis_id,
            "name": hypothesis.name,
            "description": hypothesis.description,
            "status": hypothesis.status.name,
            "entry_rules": hypothesis.entry_rules,
            "exit_rules": hypothesis.exit_rules,
            "risk_rules": hypothesis.risk_rules,
            "parameters": hypothesis.parameters,
            "best_variant": hypothesis.best_variant,
            "failure_modes": hypothesis.failure_modes,
            "tags": hypothesis.tags,
            "priority": hypothesis.priority,
            "created_at": hypothesis.created_at.isoformat(),
            "tested_at": hypothesis.tested_at.isoformat() if hypothesis.tested_at else None,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "hypotheses_count": len(self._hypotheses),
            "variants_count": len(self._variants),
            "test_results_count": len(self._test_results),
            "validated_hypotheses": sum(1 for h in self._hypotheses.values() if h.status == HypothesisStatus.VALIDATED),
            "rejected_hypotheses": sum(1 for h in self._hypotheses.values() if h.status == HypothesisStatus.REJECTED),
        })
        return status


import asyncio
