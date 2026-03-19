"""
Memory & Learning Agent

Stores lessons from wins and losses.
Tracks patterns by market regime.
Updates confidence frameworks.

Outputs:
- Pattern memory
- Setup performance maps
- Updated priors
- Lesson logs
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
from collections import defaultdict
import json

from .base_agent import BaseAgent
from .message_bus import MessageType, AgentMessage


class LessonType(Enum):
    """Type of lesson learned."""
    WIN_PATTERN = "win_pattern"
    LOSS_PATTERN = "loss_pattern"
    REGIME_INSIGHT = "regime_insight"
    SETUP_IMPROVEMENT = "setup_improvement"
    RISK_ADJUSTMENT = "risk_adjustment"
    MARKET_CONDITION = "market_condition"


class PatternConfidence(Enum):
    """Confidence level in a pattern."""
    HYPOTHESIS = "hypothesis"  # Just observed once
    EMERGING = "emerging"  # 2-3 observations
    ESTABLISHED = "established"  # 4-9 observations
    VALIDATED = "validated"  # 10+ observations


@dataclass
class Lesson:
    """A lesson learned from a trade or observation."""
    lesson_id: str
    lesson_type: LessonType
    timestamp: datetime
    
    # Context
    ticker: Optional[str]
    regime: Optional[str]
    setup_type: Optional[str]
    direction: Optional[str]
    
    # Content
    description: str
    key_observations: List[str]
    contributing_factors: List[str]
    
    # Validation
    occurrence_count: int = 1
    success_count: int = 0
    confidence: PatternConfidence = PatternConfidence.HYPOTHESIS
    
    # Impact
    impact_score: float = 0.0  # -1.0 to 1.0
    pnl_impact: float = 0.0
    
    # Metadata
    related_lessons: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class SetupPerformance:
    """Performance tracking for a specific setup."""
    setup_type: str
    direction: str
    
    # Counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Performance
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    
    # By regime
    regime_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Time decay
    recent_performance: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Confidence
    confidence_score: float = 0.5
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RegimePattern:
    """Pattern observed in a specific regime."""
    regime: str
    pattern_type: str
    
    # Observations
    observations: List[Dict] = field(default_factory=list)
    
    # Statistics
    success_rate: float = 0.0
    avg_return: float = 0.0
    sample_size: int = 0
    
    # Confidence
    confidence: PatternConfidence = PatternConfidence.HYPOTHESIS
    reliability_score: float = 0.0


@dataclass
class ConfidenceFramework:
    """Framework for confidence scoring."""
    framework_id: str
    name: str
    
    # Prior beliefs
    base_rates: Dict[str, float]
    
    # Conditional probabilities
    conditional_probs: Dict[str, Dict[str, float]]
    
    # Weights
    feature_weights: Dict[str, float]
    
    # History
    update_history: List[Dict] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


class MemoryLearningAgent(BaseAgent):
    """
    Agent for learning from trading experiences and updating beliefs.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("memory_learning", message_bus, config)
        
        # Configuration
        self.min_observations_for_pattern = config.get("min_observations", 3) if config else 3
        self.confidence_decay_days = config.get("confidence_decay", 30) if config else 30
        self.max_lessons = config.get("max_lessons", 1000) if config else 1000
        
        # Memory stores
        self._lessons: Dict[str, Lesson] = {}
        self._setup_performance: Dict[str, SetupPerformance] = {}
        self._regime_patterns: Dict[str, RegimePattern] = {}
        self._confidence_frameworks: Dict[str, ConfidenceFramework] = {}
        
        # Pattern indices
        self._patterns_by_regime: Dict[str, List[str]] = defaultdict(list)
        self._patterns_by_setup: Dict[str, List[str]] = defaultdict(list)
        self._patterns_by_ticker: Dict[str, List[str]] = defaultdict(list)
        
        # Initialize default confidence framework
        self._init_default_framework()
        
        # Register handlers
        self.register_handler(MessageType.TRADE_CLOSED, self._handle_trade_closed)
        self.register_handler(MessageType.REGIME_CHANGE, self._handle_regime_change)
        self.register_handler(MessageType.HYPOTHESIS_TESTED, self._handle_hypothesis_tested)
        
    def _init_default_framework(self):
        """Initialize default confidence framework."""
        framework = ConfidenceFramework(
            framework_id="default",
            name="Default Trading Confidence",
            base_rates={
                "win_rate": 0.50,
                "avg_return": 0.001,
                "sharpe_ratio": 1.0,
            },
            conditional_probs={
                "trending_up": {"win_rate": 0.60, "avg_return": 0.002},
                "trending_down": {"win_rate": 0.55, "avg_return": 0.0015},
                "ranging": {"win_rate": 0.45, "avg_return": 0.0005},
                "volatile": {"win_rate": 0.40, "avg_return": 0.0},
            },
            feature_weights={
                "trend_alignment": 0.25,
                "momentum": 0.20,
                "volume_confirmation": 0.15,
                "regime_stability": 0.20,
                "predictive_signal": 0.20,
            },
        )
        self._confidence_frameworks["default"] = framework
        
    async def _handle_trade_closed(self, message: AgentMessage):
        """Learn from closed trade."""
        payload = message.payload
        
        # Extract trade details
        trade_data = {
            "trade_id": payload.get("trade_id"),
            "ticker": payload.get("ticker"),
            "direction": payload.get("direction"),
            "net_pnl": payload.get("net_pnl", 0),
            "gross_pnl": payload.get("gross_pnl", 0),
            "exit_reason": payload.get("exit_reason"),
            "setup_type": payload.get("setup_type", "unknown"),
            "regime": payload.get("regime", "unknown"),
            "timestamp": payload.get("timestamp"),
        }
        
        # Learn from trade
        await self._learn_from_trade(trade_data)
        
    async def _handle_regime_change(self, message: AgentMessage):
        """Learn from regime changes."""
        payload = message.payload
        
        regime_change = {
            "ticker": payload.get("ticker"),
            "old_regime": payload.get("old_regime"),
            "new_regime": payload.get("new_regime"),
            "confidence": payload.get("confidence"),
            "timestamp": payload.get("timestamp"),
        }
        
        # Create regime insight lesson
        await self._create_regime_lesson(regime_change)
        
    async def _handle_hypothesis_tested(self, message: AgentMessage):
        """Learn from hypothesis test results."""
        payload = message.payload
        
        # Update confidence framework based on results
        hypothesis_id = payload.get("hypothesis_id")
        status = payload.get("status")
        
        if status == "VALIDATED":
            await self._update_framework_from_validation(hypothesis_id, True)
        elif status == "REJECTED":
            await self._update_framework_from_validation(hypothesis_id, False)
            
    async def _learn_from_trade(self, trade_data: Dict[str, Any]):
        """Extract lessons from a trade."""
        
        ticker = trade_data.get("ticker")
        setup_type = trade_data.get("setup_type", "unknown")
        direction = trade_data.get("direction", "long")
        regime = trade_data.get("regime", "unknown")
        pnl = trade_data.get("net_pnl", 0)
        exit_reason = trade_data.get("exit_reason", "unknown")
        
        # Update setup performance
        await self._update_setup_performance(setup_type, direction, regime, pnl)
        
        # Create lesson based on outcome
        if pnl > 0:
            await self._create_win_lesson(trade_data)
        else:
            await self._create_loss_lesson(trade_data)
            
        # Update regime patterns
        await self._update_regime_pattern(regime, setup_type, direction, pnl)
        
        # Update confidence framework
        await self._update_framework_from_trade(trade_data)
        
    async def _update_setup_performance(
        self, 
        setup_type: str, 
        direction: str, 
        regime: str, 
        pnl: float
    ):
        """Update performance tracking for a setup."""
        
        key = f"{setup_type}_{direction}"
        
        if key not in self._setup_performance:
            self._setup_performance[key] = SetupPerformance(
                setup_type=setup_type,
                direction=direction,
            )
            
        perf = self._setup_performance[key]
        perf.total_trades += 1
        perf.total_pnl += pnl
        
        if pnl > 0:
            perf.winning_trades += 1
            perf.best_trade = max(perf.best_trade, pnl)
        else:
            perf.losing_trades += 1
            perf.worst_trade = min(perf.worst_trade, pnl)
            
        perf.avg_pnl = perf.total_pnl / perf.total_trades
        
        # Update regime breakdown
        if regime not in perf.regime_performance:
            perf.regime_performance[regime] = {
                "trades": 0,
                "wins": 0,
                "total_pnl": 0,
            }
            
        perf.regime_performance[regime]["trades"] += 1
        if pnl > 0:
            perf.regime_performance[regime]["wins"] += 1
        perf.regime_performance[regime]["total_pnl"] += pnl
        
        # Update recent performance
        perf.recent_performance.append((datetime.utcnow(), pnl))
        # Keep last 50
        perf.recent_performance = perf.recent_performance[-50:]
        
        # Update confidence
        win_rate = perf.winning_trades / perf.total_trades if perf.total_trades > 0 else 0
        perf.confidence_score = win_rate * min(1.0, perf.total_trades / 20)
        perf.last_updated = datetime.utcnow()
        
    async def _create_win_lesson(self, trade_data: Dict[str, Any]):
        """Create a lesson from a winning trade."""
        
        lesson_id = f"lesson_win_{datetime.utcnow().timestamp()}"
        
        lesson = Lesson(
            lesson_id=lesson_id,
            lesson_type=LessonType.WIN_PATTERN,
            timestamp=datetime.utcnow(),
            ticker=trade_data.get("ticker"),
            regime=trade_data.get("regime"),
            setup_type=trade_data.get("setup_type"),
            direction=trade_data.get("direction"),
            description=f"Winning {trade_data.get('setup_type')} trade in {trade_data.get('regime')} regime",
            key_observations=[
                f"Exit reason: {trade_data.get('exit_reason')}",
                f"Return: {trade_data.get('net_pnl', 0):.2%}",
            ],
            contributing_factors=[],
            occurrence_count=1,
            success_count=1,
            impact_score=0.5,
            pnl_impact=trade_data.get("net_pnl", 0),
            tags=["win", trade_data.get("setup_type", ""), trade_data.get("regime", "")],
        )
        
        # Check for similar lessons to consolidate
        similar = self._find_similar_lesson(lesson)
        if similar:
            similar.occurrence_count += 1
            similar.success_count += 1
            similar.pnl_impact += lesson.pnl_impact
            similar.impact_score = (similar.impact_score * (similar.occurrence_count - 1) + 0.5) / similar.occurrence_count
            similar.last_updated = datetime.utcnow()
            await self._update_confidence_level(similar)
        else:
            self._lessons[lesson_id] = lesson
            self._index_lesson(lesson)
            
    async def _create_loss_lesson(self, trade_data: Dict[str, Any]):
        """Create a lesson from a losing trade."""
        
        lesson_id = f"lesson_loss_{datetime.utcnow().timestamp()}"
        
        lesson = Lesson(
            lesson_id=lesson_id,
            lesson_type=LessonType.LOSS_PATTERN,
            timestamp=datetime.utcnow(),
            ticker=trade_data.get("ticker"),
            regime=trade_data.get("regime"),
            setup_type=trade_data.get("setup_type"),
            direction=trade_data.get("direction"),
            description=f"Losing {trade_data.get('setup_type')} trade in {trade_data.get('regime')} regime",
            key_observations=[
                f"Exit reason: {trade_data.get('exit_reason')}",
                f"Loss: {trade_data.get('net_pnl', 0):.2%}",
            ],
            contributing_factors=[],
            occurrence_count=1,
            success_count=0,
            impact_score=-0.5,
            pnl_impact=trade_data.get("net_pnl", 0),
            tags=["loss", trade_data.get("setup_type", ""), trade_data.get("regime", "")],
        )
        
        # Check for similar lessons
        similar = self._find_similar_lesson(lesson)
        if similar:
            similar.occurrence_count += 1
            similar.pnl_impact += lesson.pnl_impact
            similar.impact_score = (similar.impact_score * (similar.occurrence_count - 1) - 0.5) / similar.occurrence_count
            similar.last_updated = datetime.utcnow()
            await self._update_confidence_level(similar)
        else:
            self._lessons[lesson_id] = lesson
            self._index_lesson(lesson)
            
    async def _create_regime_lesson(self, regime_change: Dict[str, Any]):
        """Create a lesson from regime change."""
        
        lesson_id = f"lesson_regime_{datetime.utcnow().timestamp()}"
        
        lesson = Lesson(
            lesson_id=lesson_id,
            lesson_type=LessonType.REGIME_INSIGHT,
            timestamp=datetime.utcnow(),
            ticker=regime_change.get("ticker"),
            regime=regime_change.get("new_regime"),
            setup_type=None,
            direction=None,
            description=f"Regime change from {regime_change.get('old_regime')} to {regime_change.get('new_regime')}",
            key_observations=[
                f"Confidence: {regime_change.get('confidence', 0):.2f}",
            ],
            contributing_factors=[],
            tags=["regime_change", regime_change.get("new_regime", "")],
        )
        
        self._lessons[lesson_id] = lesson
        self._index_lesson(lesson)
        
    async def _update_regime_pattern(
        self, 
        regime: str, 
        setup_type: str, 
        direction: str, 
        pnl: float
    ):
        """Update pattern tracking for a regime."""
        
        key = f"{regime}_{setup_type}_{direction}"
        
        if key not in self._regime_patterns:
            self._regime_patterns[key] = RegimePattern(
                regime=regime,
                pattern_type=f"{setup_type}_{direction}",
            )
            
        pattern = self._regime_patterns[key]
        pattern.observations.append({
            "timestamp": datetime.utcnow(),
            "pnl": pnl,
        })
        
        pattern.sample_size += 1
        
        # Recalculate statistics
        pnls = [o["pnl"] for o in pattern.observations]
        wins = [p for p in pnls if p > 0]
        
        pattern.success_rate = len(wins) / len(pnls) if pnls else 0
        pattern.avg_return = np.mean(pnls) if pnls else 0
        
        # Update confidence
        await self._update_pattern_confidence(pattern)
        
        # Calculate reliability
        if pattern.sample_size >= 10:
            pattern.reliability_score = pattern.success_rate * (1 - np.std(pnls) / (abs(np.mean(pnls)) + 0.001))
        else:
            pattern.reliability_score = pattern.success_rate * (pattern.sample_size / 10)
            
    async def _update_pattern_confidence(self, pattern: RegimePattern):
        """Update confidence level based on sample size."""
        if pattern.sample_size >= 10:
            pattern.confidence = PatternConfidence.VALIDATED
        elif pattern.sample_size >= 4:
            pattern.confidence = PatternConfidence.ESTABLISHED
        elif pattern.sample_size >= 2:
            pattern.confidence = PatternConfidence.EMERGING
        else:
            pattern.confidence = PatternConfidence.HYPOTHESIS
            
    async def _update_confidence_level(self, lesson: Lesson):
        """Update confidence level of a lesson."""
        if lesson.occurrence_count >= 10:
            lesson.confidence = PatternConfidence.VALIDATED
        elif lesson.occurrence_count >= 4:
            lesson.confidence = PatternConfidence.ESTABLISHED
        elif lesson.occurrence_count >= 2:
            lesson.confidence = PatternConfidence.EMERGING
            
    def _find_similar_lesson(self, lesson: Lesson) -> Optional[Lesson]:
        """Find a similar existing lesson."""
        for existing in self._lessons.values():
            if (existing.lesson_type == lesson.lesson_type and
                existing.setup_type == lesson.setup_type and
                existing.regime == lesson.regime and
                existing.direction == lesson.direction):
                return existing
        return None
        
    def _index_lesson(self, lesson: Lesson):
        """Index lesson for quick lookup."""
        if lesson.regime:
            self._patterns_by_regime[lesson.regime].append(lesson.lesson_id)
        if lesson.setup_type:
            self._patterns_by_setup[lesson.setup_type].append(lesson.lesson_id)
        if lesson.ticker:
            self._patterns_by_ticker[lesson.ticker].append(lesson.lesson_id)
            
    async def _update_framework_from_trade(self, trade_data: Dict[str, Any]):
        """Update confidence framework based on trade outcome."""
        
        framework = self._confidence_frameworks.get("default")
        if not framework:
            return
            
        regime = trade_data.get("regime", "unknown")
        pnl = trade_data.get("net_pnl", 0)
        
        # Update base rates with Bayesian approach
        if regime in framework.conditional_probs:
            current = framework.conditional_probs[regime]
            
            # Update win rate (simplified Bayesian update)
            prior_wins = current["win_rate"] * 100
            if pnl > 0:
                new_win_rate = (prior_wins + 1) / 101
            else:
                new_win_rate = prior_wins / 101
                
            current["win_rate"] = new_win_rate
            
            # Update avg return
            current["avg_return"] = (current["avg_return"] * 99 + pnl) / 100
            
        framework.last_updated = datetime.utcnow()
        framework.update_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "trigger": "trade_closed",
            "regime": regime,
        })
        
    async def _update_framework_from_validation(self, hypothesis_id: str, validated: bool):
        """Update framework based on hypothesis validation."""
        
        framework = self._confidence_frameworks.get("default")
        if not framework:
            return
            
        # Adjust feature weights based on validation
        if validated:
            # Increase confidence in used features
            for feature in framework.feature_weights:
                framework.feature_weights[feature] *= 1.01
        else:
            # Decrease confidence
            for feature in framework.feature_weights:
                framework.feature_weights[feature] *= 0.99
                
        # Normalize weights
        total = sum(framework.feature_weights.values())
        if total > 0:
            framework.feature_weights = {k: v/total for k, v in framework.feature_weights.items()}
            
    async def get_setup_recommendation(self, setup_type: str, direction: str, regime: str) -> Dict[str, Any]:
        """Get recommendation for a setup based on learned patterns."""
        
        key = f"{setup_type}_{direction}"
        perf = self._setup_performance.get(key)
        
        if not perf or perf.total_trades < self.min_observations_for_pattern:
            return {
                "setup_type": setup_type,
                "direction": direction,
                "recommendation": "insufficient_data",
                "confidence": 0.5,
            }
            
        # Check regime-specific performance
        regime_perf = perf.regime_performance.get(regime, {})
        regime_trades = regime_perf.get("trades", 0)
        regime_wins = regime_perf.get("wins", 0)
        regime_win_rate = regime_wins / regime_trades if regime_trades > 0 else 0.5
        
        # Get relevant lessons
        lesson_ids = self._patterns_by_setup.get(setup_type, [])
        relevant_lessons = [
            self._lessons[lid] for lid in lesson_ids
            if self._lessons[lid].regime == regime
        ]
        
        # Calculate recommendation
        if regime_win_rate > 0.6 and perf.confidence_score > 0.5:
            recommendation = "favorable"
        elif regime_win_rate < 0.4:
            recommendation = "avoid"
        else:
            recommendation = "neutral"
            
        return {
            "setup_type": setup_type,
            "direction": direction,
            "regime": regime,
            "recommendation": recommendation,
            "confidence": perf.confidence_score,
            "historical_win_rate": regime_win_rate,
            "total_trades": perf.total_trades,
            "regime_trades": regime_trades,
            "avg_pnl": perf.avg_pnl,
            "lessons_count": len(relevant_lessons),
        }
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        
        if task_type == "get_setup_recommendation":
            setup_type = task.get("setup_type")
            direction = task.get("direction")
            regime = task.get("regime")
            return await self.get_setup_recommendation(setup_type, direction, regime)
            
        elif task_type == "get_lessons":
            lesson_type = task.get("lesson_type")
            regime = task.get("regime")
            
            lessons = list(self._lessons.values())
            if lesson_type:
                lessons = [l for l in lessons if l.lesson_type.value == lesson_type]
            if regime:
                lessons = [l for l in lessons if l.regime == regime]
                
            return {
                "lessons": [
                    {
                        "lesson_id": l.lesson_id,
                        "type": l.lesson_type.value,
                        "description": l.description,
                        "confidence": l.confidence.value,
                        "occurrence_count": l.occurrence_count,
                        "impact_score": l.impact_score,
                    }
                    for l in lessons[-50:]
                ]
            }
            
        elif task_type == "get_setup_performance":
            setup_type = task.get("setup_type")
            if setup_type:
                perfs = [
                    perf for key, perf in self._setup_performance.items()
                    if perf.setup_type == setup_type
                ]
            else:
                perfs = list(self._setup_performance.values())
                
            return {
                "setups": [
                    {
                        "setup_type": p.setup_type,
                        "direction": p.direction,
                        "total_trades": p.total_trades,
                        "win_rate": p.winning_trades / p.total_trades if p.total_trades > 0 else 0,
                        "avg_pnl": p.avg_pnl,
                        "confidence_score": p.confidence_score,
                    }
                    for p in perfs
                ]
            }
            
        elif task_type == "get_regime_patterns":
            regime = task.get("regime")
            if regime:
                patterns = [
                    p for key, p in self._regime_patterns.items()
                    if p.regime == regime
                ]
            else:
                patterns = list(self._regime_patterns.values())
                
            return {
                "patterns": [
                    {
                        "regime": p.regime,
                        "pattern_type": p.pattern_type,
                        "sample_size": p.sample_size,
                        "success_rate": p.success_rate,
                        "avg_return": p.avg_return,
                        "confidence": p.confidence.value,
                        "reliability_score": p.reliability_score,
                    }
                    for p in patterns
                ]
            }
            
        elif task_type == "get_confidence_framework":
            framework_id = task.get("framework_id", "default")
            framework = self._confidence_frameworks.get(framework_id)
            
            if framework:
                return {
                    "framework": {
                        "framework_id": framework.framework_id,
                        "name": framework.name,
                        "base_rates": framework.base_rates,
                        "conditional_probs": framework.conditional_probs,
                        "feature_weights": framework.feature_weights,
                        "last_updated": framework.last_updated.isoformat(),
                    }
                }
            return {"error": "Framework not found"}
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        status.update({
            "lessons_count": len(self._lessons),
            "setup_performance_count": len(self._setup_performance),
            "regime_patterns_count": len(self._regime_patterns),
            "confidence_frameworks_count": len(self._confidence_frameworks),
        })
        return status


import asyncio
