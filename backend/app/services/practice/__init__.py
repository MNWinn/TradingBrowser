"""Practice Trading Services Module.

This module provides paper trading functionality including:
- Virtual portfolio management
- Paper trade execution
- Strategy implementations
- Performance evaluation
- Trading challenges and achievements
"""

from app.services.practice.practice_engine import (
    PracticeEngine,
    PracticePortfolio,
    PracticePosition,
    PracticeTrade,
    PracticeTradeStatus,
    PracticePositionSide,
    get_practice_engine,
)

from app.services.practice.practice_strategies import (
    BaseStrategy,
    MiroFishStrategy,
    TechnicalIndicatorStrategy,
    MultiAgentConsensusStrategy,
    CustomStrategyBuilder,
    StrategyRecommendation,
    StrategySignal,
    get_strategy,
    list_available_strategies,
    STRATEGY_REGISTRY,
)

from app.services.practice.practice_evaluation import (
    PracticeEvaluator,
    TradePerformance,
    PeriodPerformance,
    DrawdownPeriod,
    StrategyComparison,
    TradeOutcome,
    get_practice_evaluator,
)

from app.services.practice.practice_challenges import (
    ChallengeManager,
    Challenge,
    Achievement,
    DailyChallengeSet,
    ChallengeType,
    ChallengeStatus,
    AchievementTier,
    get_challenge_manager,
)

__all__ = [
    # Engine
    "PracticeEngine",
    "PracticePortfolio",
    "PracticePosition",
    "PracticeTrade",
    "PracticeTradeStatus",
    "PracticePositionSide",
    "get_practice_engine",
    
    # Strategies
    "BaseStrategy",
    "MiroFishStrategy",
    "TechnicalIndicatorStrategy",
    "MultiAgentConsensusStrategy",
    "CustomStrategyBuilder",
    "StrategyRecommendation",
    "StrategySignal",
    "get_strategy",
    "list_available_strategies",
    "STRATEGY_REGISTRY",
    
    # Evaluation
    "PracticeEvaluator",
    "TradePerformance",
    "PeriodPerformance",
    "DrawdownPeriod",
    "StrategyComparison",
    "TradeOutcome",
    "get_practice_evaluator",
    
    # Challenges
    "ChallengeManager",
    "Challenge",
    "Achievement",
    "DailyChallengeSet",
    "ChallengeType",
    "ChallengeStatus",
    "AchievementTier",
    "get_challenge_manager",
]
