"""
Evaluation Agent

Studies results across hundreds of trades.
Measures robustness (not just profit).
Identifies regime dependency and overfitting.

Outputs:
- Scorecards
- Reliability analysis
- Stability metrics
- Graduation readiness
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
from collections import defaultdict
import statistics

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class MetricGrade(Enum):
    """Grade for a metric."""
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"


@dataclass
class TradeMetrics:
    """Metrics calculated from a set of trades."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_loss_ratio: float = 0.0
    
    total_return: float = 0.0
    avg_return: float = 0.0
    return_std: float = 0.0
    
    max_drawdown: float = 0.0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    
    avg_holding_time_hours: float = 0.0


@dataclass
class RegimePerformance:
    """Performance breakdown by market regime."""
    regime: str
    trade_count: int
    win_rate: float
    avg_return: float
    total_return: float
    sharpe_ratio: float
    consistency_score: float  # How consistent within regime


@dataclass
class RobustnessMetrics:
    """Robustness and stability metrics."""
    # Walk-forward efficiency
    walk_forward_efficiency: float = 0.0
    
    # Regime robustness
    regime_consistency: float = 0.0  # Low variance across regimes
    worst_regime_return: float = 0.0
    
    # Time stability
    period_consistency: float = 0.0  # Consistent across time periods
    
    # Statistical significance
    t_statistic: float = 0.0
    p_value: float = 1.0
    is_statistically_significant: bool = False
    
    # Overfitting indicators
    parameter_sensitivity: float = 0.0  # Lower is better
    degrees_of_freedom_ratio: float = 0.0  # Trades / parameters
    
    # Sample size adequacy
    sample_size_adequate: bool = False
    minimum_trades_recommended: int = 100


@dataclass
class Scorecard:
    """Complete evaluation scorecard."""
    scorecard_id: str
    strategy_id: str
    timestamp: datetime
    
    # Trade metrics
    metrics: TradeMetrics
    
    # Regime breakdown
    regime_performance: Dict[str, RegimePerformance]
    
    # Robustness
    robustness: RobustnessMetrics
    
    # Grades
    profitability_grade: MetricGrade
    consistency_grade: MetricGrade
    robustness_grade: MetricGrade
    risk_adjusted_grade: MetricGrade
    overall_grade: MetricGrade
    
    # Scores (0-100)
    profitability_score: float
    consistency_score: float
    robustness_score: float
    risk_adjusted_score: float
    overall_score: float
    
    # Graduation readiness
    graduation_ready: bool
    graduation_blockers: List[str]
    graduation_recommendations: List[str]
    
    # Analysis
    strengths: List[str]
    weaknesses: List[str]
    anomalies: List[str]
    
    # Metadata
    trade_sample_size: int
    evaluation_period_days: int


class EvaluationAgent(BaseAgent):
    """
    Agent for comprehensive strategy evaluation and graduation assessment.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("evaluation", message_bus, config)
        
        # Configuration
        self.min_trades_for_evaluation = config.get("min_trades", 50) if config else 50
        self.min_graduation_trades = config.get("min_graduation_trades", 100) if config else 100
        self.confidence_level = config.get("confidence_level", 0.95) if config else 0.95
        
        # State
        self._scorecards: Dict[str, Scorecard] = {}
        self._scorecard_history: List[Scorecard] = []
        self._trade_data: Dict[str, List[Dict]] = defaultdict(list)
        self._regime_data: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        
        # Register handlers
        self.register_handler(MessageType.TRADE_CLOSED, self._handle_trade_closed)
        self.register_handler(MessageType.RESEARCH_RESULTS, self._handle_research_results)
        
    async def _handle_trade_closed(self, message: AgentMessage):
        """Handle closed trade for evaluation."""
        payload = message.payload
        strategy_id = payload.get("strategy_id", "default")
        
        # Store trade data
        self._trade_data[strategy_id].append(payload)
        
        # Store by regime if available
        regime = payload.get("regime", "unknown")
        self._regime_data[strategy_id][regime].append(payload)
        
        # Check if we should run evaluation
        if len(self._trade_data[strategy_id]) >= self.min_trades_for_evaluation:
            if len(self._trade_data[strategy_id]) % 25 == 0:  # Every 25 trades
                await self.evaluate_strategy(strategy_id)
                
    async def _handle_research_results(self, message: AgentMessage):
        """Handle research results for evaluation."""
        payload = message.payload
        hypothesis_id = payload.get("hypothesis_id")
        
        if hypothesis_id:
            # Can trigger evaluation of research results
            pass
            
    async def evaluate_strategy(self, strategy_id: str) -> Scorecard:
        """Run comprehensive evaluation on a strategy."""
        
        trades = self._trade_data.get(strategy_id, [])
        
        if len(trades) < self.min_trades_for_evaluation:
            return None
            
        # Calculate trade metrics
        metrics = self._calculate_trade_metrics(trades)
        
        # Calculate regime performance
        regime_perf = self._calculate_regime_performance(strategy_id)
        
        # Calculate robustness
        robustness = self._calculate_robustness(trades, regime_perf)
        
        # Calculate grades
        profitability_grade, profitability_score = self._grade_profitability(metrics)
        consistency_grade, consistency_score = self._grade_consistency(metrics)
        robustness_grade, robustness_score = self._grade_robustness(robustness)
        risk_grade, risk_score = self._grade_risk_adjusted(metrics)
        
        overall_score = (profitability_score + consistency_score + robustness_score + risk_score) / 4
        overall_grade = self._score_to_grade(overall_score)
        
        # Check graduation readiness
        graduation_ready, blockers, recommendations = self._check_graduation_readiness(
            metrics, robustness, overall_score
        )
        
        # Identify strengths and weaknesses
        strengths, weaknesses, anomalies = self._analyze_performance(trades, metrics, regime_perf)
        
        scorecard = Scorecard(
            scorecard_id=f"sc_{strategy_id}_{datetime.utcnow().timestamp()}",
            strategy_id=strategy_id,
            timestamp=datetime.utcnow(),
            metrics=metrics,
            regime_performance=regime_perf,
            robustness=robustness,
            profitability_grade=profitability_grade,
            consistency_grade=consistency_grade,
            robustness_grade=robustness_grade,
            risk_adjusted_grade=risk_grade,
            overall_grade=overall_grade,
            profitability_score=profitability_score,
            consistency_score=consistency_score,
            robustness_score=robustness_score,
            risk_adjusted_score=risk_score,
            overall_score=overall_score,
            graduation_ready=graduation_ready,
            graduation_blockers=blockers,
            graduation_recommendations=recommendations,
            strengths=strengths,
            weaknesses=weaknesses,
            anomalies=anomalies,
            trade_sample_size=len(trades),
            evaluation_period_days=self._calculate_evaluation_period(trades),
        )
        
        self._scorecards[strategy_id] = scorecard
        self._scorecard_history.append(scorecard)
        
        # Publish evaluation complete
        await self._publish_evaluation(scorecard)
        
        return scorecard
        
    def _calculate_trade_metrics(self, trades: List[Dict]) -> TradeMetrics:
        """Calculate metrics from trade list."""
        
        if not trades:
            return TradeMetrics()
            
        returns = [t.get("net_pnl", 0) for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        
        # Basic counts
        total = len(trades)
        winning = len(wins)
        losing = len(losses)
        win_rate = winning / total if total > 0 else 0
        
        # Returns
        total_return = sum(returns)
        avg_return = np.mean(returns) if returns else 0
        return_std = np.std(returns) if len(returns) > 1 else 0
        
        # Win/loss
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        
        # Drawdown calculation
        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / (peak + 1e-10)
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        
        # Consecutive
        max_consec_losses = 0
        max_consec_wins = 0
        current_losses = 0
        current_wins = 0
        
        for r in returns:
            if r > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
                
        # Ratios
        sharpe = avg_return / return_std * np.sqrt(252) if return_std > 0 else 0  # Annualized
        
        downside_returns = [r for r in returns if r < 0]
        downside_std = np.std(downside_returns) if len(downside_returns) > 1 else 1e-10
        sortino = avg_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
        
        calmar = avg_return * 252 / max_dd if max_dd > 0 else 0
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Holding time
        holding_times = []
        for t in trades:
            opened = t.get("opened_at")
            closed = t.get("closed_at")
            if opened and closed:
                try:
                    opened_dt = datetime.fromisoformat(opened.replace('Z', '+00:00'))
                    closed_dt = datetime.fromisoformat(closed.replace('Z', '+00:00'))
                    hours = (closed_dt - opened_dt).total_seconds() / 3600
                    holding_times.append(hours)
                except:
                    pass
                    
        avg_holding = np.mean(holding_times) if holding_times else 0
        
        return TradeMetrics(
            total_trades=total,
            winning_trades=winning,
            losing_trades=losing,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_loss_ratio=win_loss_ratio,
            total_return=total_return,
            avg_return=avg_return,
            return_std=return_std,
            max_drawdown=max_dd,
            max_consecutive_losses=max_consec_losses,
            max_consecutive_wins=max_consec_wins,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            profit_factor=profit_factor,
            avg_holding_time_hours=avg_holding,
        )
        
    def _calculate_regime_performance(self, strategy_id: str) -> Dict[str, RegimePerformance]:
        """Calculate performance by regime."""
        regime_data = self._regime_data.get(strategy_id, {})
        
        results = {}
        for regime, trades in regime_data.items():
            if len(trades) < 5:
                continue
                
            returns = [t.get("net_pnl", 0) for t in trades]
            wins = [r for r in returns if r > 0]
            
            win_rate = len(wins) / len(returns) if returns else 0
            avg_return = np.mean(returns) if returns else 0
            total_return = sum(returns)
            
            return_std = np.std(returns) if len(returns) > 1 else 1e-10
            sharpe = avg_return / return_std * np.sqrt(252) if return_std > 0 else 0
            
            # Consistency within regime
            consistency = 1 - (return_std / (abs(avg_return) + 1e-10)) if avg_return != 0 else 0
            
            results[regime] = RegimePerformance(
                regime=regime,
                trade_count=len(trades),
                win_rate=win_rate,
                avg_return=avg_return,
                total_return=total_return,
                sharpe_ratio=sharpe,
                consistency_score=max(0, consistency),
            )
            
        return results
        
    def _calculate_robustness(
        self, 
        trades: List[Dict], 
        regime_perf: Dict[str, RegimePerformance]
    ) -> RobustnessMetrics:
        """Calculate robustness metrics."""
        
        returns = [t.get("net_pnl", 0) for t in trades]
        
        # Statistical significance (t-test)
        if len(returns) > 1:
            t_stat = np.mean(returns) / (np.std(returns) / np.sqrt(len(returns)))
            # Approximate p-value (simplified)
            p_value = 0.05  # Would use proper t-distribution
            is_significant = abs(t_stat) > 2.0  # Rough 95% confidence
        else:
            t_stat = 0
            p_value = 1.0
            is_significant = False
            
        # Regime consistency
        if regime_perf:
            regime_returns = [p.total_return for p in regime_perf.values()]
            regime_consistency = 1 - (np.std(regime_returns) / (abs(np.mean(regime_returns)) + 1e-10))
            worst_regime = min(regime_returns)
        else:
            regime_consistency = 0
            worst_regime = 0
            
        # Sample size adequacy
        sample_adequate = len(trades) >= self.min_graduation_trades
        
        return RobustnessMetrics(
            walk_forward_efficiency=0.7,  # Would calculate from walk-forward tests
            regime_consistency=max(0, regime_consistency),
            worst_regime_return=worst_regime,
            period_consistency=0.75,  # Would calculate from time periods
            t_statistic=t_stat,
            p_value=p_value,
            is_statistically_significant=is_significant,
            parameter_sensitivity=0.3,  # Would calculate from parameter sweeps
            degrees_of_freedom_ratio=len(trades) / 10,  # Assume 10 parameters
            sample_size_adequate=sample_adequate,
            minimum_trades_recommended=self.min_graduation_trades,
        )
        
    def _grade_profitability(self, metrics: TradeMetrics) -> Tuple[MetricGrade, float]:
        """Grade profitability."""
        score = 0
        
        # Win rate (30%)
        score += min(metrics.win_rate * 100, 70) / 70 * 30
        
        # Total return (40%)
        return_score = min(metrics.total_return * 100, 50) / 50 * 40
        score += return_score
        
        # Profit factor (30%)
        pf_score = min(metrics.profit_factor, 2.0) / 2.0 * 30
        score += pf_score
        
        return self._score_to_grade(score), score
        
    def _grade_consistency(self, metrics: TradeMetrics) -> Tuple[MetricGrade, float]:
        """Grade consistency."""
        score = 0
        
        # Win/loss ratio (40%)
        wl_score = min(metrics.win_loss_ratio, 3.0) / 3.0 * 40
        score += wl_score
        
        # Max consecutive losses (30%)
        cl_score = max(0, 1 - metrics.max_consecutive_losses / 10) * 30
        score += cl_score
        
        # Return consistency (30%)
        if metrics.avg_return > 0:
            consistency = 1 - min(metrics.return_std / metrics.avg_return, 1)
        else:
            consistency = 0
        score += consistency * 30
        
        return self._score_to_grade(score), score
        
    def _grade_robustness(self, robustness: RobustnessMetrics) -> Tuple[MetricGrade, float]:
        """Grade robustness."""
        score = 0
        
        # Statistical significance (30%)
        score += 30 if robustness.is_statistically_significant else 10
        
        # Regime consistency (30%)
        score += robustness.regime_consistency * 30
        
        # Sample size (20%)
        ss_score = min(robustness.degrees_of_freedom_ratio / 10, 1) * 20
        score += ss_score
        
        # Worst regime (20%)
        if robustness.worst_regime_return > -0.05:
            score += 20
        elif robustness.worst_regime_return > -0.10:
            score += 10
            
        return self._score_to_grade(score), score
        
    def _grade_risk_adjusted(self, metrics: TradeMetrics) -> Tuple[MetricGrade, float]:
        """Grade risk-adjusted returns."""
        score = 0
        
        # Sharpe ratio (40%)
        sharpe_score = min(max(metrics.sharpe_ratio, 0), 2.0) / 2.0 * 40
        score += sharpe_score
        
        # Sortino ratio (30%)
        sortino_score = min(max(metrics.sortino_ratio, 0), 3.0) / 3.0 * 30
        score += sortino_score
        
        # Max drawdown (30%)
        dd_score = max(0, 1 - metrics.max_drawdown / 0.20) * 30
        score += dd_score
        
        return self._score_to_grade(score), score
        
    def _score_to_grade(self, score: float) -> MetricGrade:
        """Convert score to grade."""
        if score >= 95:
            return MetricGrade.A_PLUS
        elif score >= 85:
            return MetricGrade.A
        elif score >= 78:
            return MetricGrade.B_PLUS
        elif score >= 70:
            return MetricGrade.B
        elif score >= 65:
            return MetricGrade.C_PLUS
        elif score >= 60:
            return MetricGrade.C
        elif score >= 50:
            return MetricGrade.D
        else:
            return MetricGrade.F
            
    def _check_graduation_readiness(
        self,
        metrics: TradeMetrics,
        robustness: RobustnessMetrics,
        overall_score: float
    ) -> Tuple[bool, List[str], List[str]]:
        """Check if strategy is ready for graduation to live trading."""
        
        blockers = []
        recommendations = []
        
        # Sample size
        if metrics.total_trades < self.min_graduation_trades:
            blockers.append(f"Insufficient trade sample: {metrics.total_trades}/{self.min_graduation_trades}")
            
        # Statistical significance
        if not robustness.is_statistically_significant:
            blockers.append("Results not statistically significant")
            
        # Profitability
        if metrics.total_return <= 0:
            blockers.append("Strategy not profitable")
            
        # Win rate
        if metrics.win_rate < 0.45:
            recommendations.append("Win rate below 45% - review entry criteria")
            
        # Drawdown
        if metrics.max_drawdown > 0.15:
            recommendations.append("Max drawdown exceeds 15% - tighten risk controls")
            
        # Regime robustness
        if robustness.worst_regime_return < -0.10:
            recommendations.append("Poor performance in some regimes - consider regime filters")
            
        # Overall score
        if overall_score < 70:
            recommendations.append("Overall score below 70 - continue research and refinement")
            
        ready = len(blockers) == 0 and overall_score >= 70
        
        return ready, blockers, recommendations
        
    def _analyze_performance(
        self,
        trades: List[Dict],
        metrics: TradeMetrics,
        regime_perf: Dict[str, RegimePerformance]
    ) -> Tuple[List[str], List[str], List[str]]:
        """Analyze performance for strengths, weaknesses, and anomalies."""
        
        strengths = []
        weaknesses = []
        anomalies = []
        
        # Strengths
        if metrics.win_rate > 0.55:
            strengths.append(f"Strong win rate: {metrics.win_rate:.1%}")
        if metrics.sharpe_ratio > 1.5:
            strengths.append(f"Excellent risk-adjusted returns: Sharpe {metrics.sharpe_ratio:.2f}")
        if metrics.profit_factor > 2.0:
            strengths.append(f"Strong profit factor: {metrics.profit_factor:.2f}")
        if len(regime_perf) >= 3:
            strengths.append("Tested across multiple market regimes")
            
        # Weaknesses
        if metrics.max_drawdown > 0.10:
            weaknesses.append(f"High maximum drawdown: {metrics.max_drawdown:.1%}")
        if metrics.max_consecutive_losses > 5:
            weaknesses.append(f"Long losing streaks: {metrics.max_consecutive_losses} consecutive losses")
        if metrics.win_loss_ratio < 1.0:
            weaknesses.append(f"Poor win/loss ratio: {metrics.win_loss_ratio:.2f}")
            
        # Anomalies
        returns = [t.get("net_pnl", 0) for t in trades]
        if returns:
            z_scores = [(r - np.mean(returns)) / np.std(returns) for r in returns if np.std(returns) > 0]
            outliers = [z for z in z_scores if abs(z) > 3]
            if outliers:
                anomalies.append(f"Found {len(outliers)} statistical outliers in returns")
                
        return strengths, weaknesses, anomalies
        
    def _calculate_evaluation_period(self, trades: List[Dict]) -> int:
        """Calculate evaluation period in days."""
        if not trades:
            return 0
            
        timestamps = []
        for t in trades:
            ts = t.get("timestamp") or t.get("closed_at")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    timestamps.append(dt)
                except:
                    pass
                    
        if len(timestamps) >= 2:
            return (max(timestamps) - min(timestamps)).days
        return 0
        
    async def _publish_evaluation(self, scorecard: Scorecard):
        """Publish evaluation results."""
        await self.send_message(
            MessageType.EVALUATION_COMPLETE,
            {
                "scorecard_id": scorecard.scorecard_id,
                "strategy_id": scorecard.strategy_id,
                "timestamp": scorecard.timestamp.isoformat(),
                "overall_grade": scorecard.overall_grade.value,
                "overall_score": scorecard.overall_score,
                "graduation_ready": scorecard.graduation_ready,
                "trade_sample_size": scorecard.trade_sample_size,
                "metrics": {
                    "win_rate": scorecard.metrics.win_rate,
                    "total_return": scorecard.metrics.total_return,
                    "sharpe_ratio": scorecard.metrics.sharpe_ratio,
                    "max_drawdown": scorecard.metrics.max_drawdown,
                    "profit_factor": scorecard.metrics.profit_factor,
                },
                "graduation_blockers": scorecard.graduation_blockers,
            }
        )
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        strategy_id = task.get("strategy_id", "default")
        
        if task_type == "evaluate":
            scorecard = await self.evaluate_strategy(strategy_id)
            return {
                "scorecard": self._scorecard_to_dict(scorecard) if scorecard else None
            }
            
        elif task_type == "get_scorecard":
            scorecard = self._scorecards.get(strategy_id)
            return {
                "scorecard": self._scorecard_to_dict(scorecard) if scorecard else None
            }
            
        elif task_type == "get_all_scorecards":
            return {
                "scorecards": [
                    self._scorecard_to_dict(sc) for sc in self._scorecards.values()
                ]
            }
            
        elif task_type == "compare_strategies":
            strategy_ids = task.get("strategy_ids", [])
            comparison = {}
            for sid in strategy_ids:
                sc = self._scorecards.get(sid)
                if sc:
                    comparison[sid] = {
                        "overall_score": sc.overall_score,
                        "overall_grade": sc.overall_grade.value,
                        "total_return": sc.metrics.total_return,
                        "sharpe_ratio": sc.metrics.sharpe_ratio,
                    }
            return {"comparison": comparison}
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def _scorecard_to_dict(self, scorecard: Scorecard) -> Dict[str, Any]:
        """Convert scorecard to dictionary."""
        if not scorecard:
            return None
        return {
            "scorecard_id": scorecard.scorecard_id,
            "strategy_id": scorecard.strategy_id,
            "timestamp": scorecard.timestamp.isoformat(),
            "overall_grade": scorecard.overall_grade.value,
            "overall_score": scorecard.overall_score,
            "profitability": {
                "grade": scorecard.profitability_grade.value,
                "score": scorecard.profitability_score,
            },
            "consistency": {
                "grade": scorecard.consistency_grade.value,
                "score": scorecard.consistency_score,
            },
            "robustness": {
                "grade": scorecard.robustness_grade.value,
                "score": scorecard.robustness_score,
            },
            "risk_adjusted": {
                "grade": scorecard.risk_adjusted_grade.value,
                "score": scorecard.risk_adjusted_score,
            },
            "metrics": {
                "total_trades": scorecard.metrics.total_trades,
                "win_rate": scorecard.metrics.win_rate,
                "total_return": scorecard.metrics.total_return,
                "sharpe_ratio": scorecard.metrics.sharpe_ratio,
                "max_drawdown": scorecard.metrics.max_drawdown,
                "profit_factor": scorecard.metrics.profit_factor,
            },
            "graduation_ready": scorecard.graduation_ready,
            "graduation_blockers": scorecard.graduation_blockers,
            "strengths": scorecard.strengths,
            "weaknesses": scorecard.weaknesses,
            "trade_sample_size": scorecard.trade_sample_size,
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "scorecards_count": len(self._scorecards),
            "scorecard_history_count": len(self._scorecard_history),
            "strategies_tracked": list(self._trade_data.keys()),
            "total_trades_evaluated": sum(len(t) for t in self._trade_data.values()),
        })
        return status


import asyncio
