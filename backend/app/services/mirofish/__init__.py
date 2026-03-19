"""
MiroFish Advanced Integration Layer

This package provides advanced MiroFish integration capabilities:

- **mirofish_fleet**: Multi-timeframe, multi-lens assessment management
- **mirofish_cache**: Redis-based caching with TTL management
- **mirofish_ensemble**: Ensemble decision making with other agents
- **mirofish_practice**: Paper trading practice mode

Usage:
    from app.services.mirofish import (
        get_fleet,
        get_cache,
        get_ensemble,
        get_practice,
        fleet_analyze,
        cached_assessment,
        ensemble_decision,
    )
"""

from app.services.mirofish.mirofish_fleet import (
    MiroFishFleet,
    FleetAnalysis,
    MiroFishAssessment,
    DirectionalBias,
    Timeframe,
    Lens,
    ConfidenceAggregator,
    DisagreementDetector,
    get_fleet,
    fleet_analyze,
    fleet_quick,
    fleet_deep,
)

from app.services.mirofish.mirofish_cache import (
    MiroFishCache,
    CacheEntry,
    CacheConfig,
    CacheStrategy,
    get_cache,
    cached_assessment,
    invalidate_ticker_cache,
    get_cache_stats,
)

from app.services.mirofish.mirofish_ensemble import (
    MiroFishEnsemble,
    EnsembleResult,
    AgentSignal,
    SignalSource,
    Action,
    WeightConfig,
    HistoricalAccuracyTracker,
    DynamicWeightAdjuster,
    ConflictResolver,
    get_ensemble,
    ensemble_decision,
    create_agent_signal,
)

from app.services.mirofish.mirofish_practice import (
    MiroFishPractice,
    PracticeSession,
    PracticeTrade,
    MiroFishConfig,
    TradeStatus,
    TradeDirection,
    ExitReason,
    get_practice,
    create_practice_session,
    evaluate_trade_entry,
    simulate_trade,
    close_trade,
    get_session_results,
    get_available_configs,
    DEFAULT_CONFIGS,
)

__all__ = [
    # Fleet
    "MiroFishFleet",
    "FleetAnalysis",
    "MiroFishAssessment",
    "DirectionalBias",
    "Timeframe",
    "Lens",
    "ConfidenceAggregator",
    "DisagreementDetector",
    "get_fleet",
    "fleet_analyze",
    "fleet_quick",
    "fleet_deep",
    
    # Cache
    "MiroFishCache",
    "CacheEntry",
    "CacheConfig",
    "CacheStrategy",
    "get_cache",
    "cached_assessment",
    "invalidate_ticker_cache",
    "get_cache_stats",
    
    # Ensemble
    "MiroFishEnsemble",
    "EnsembleResult",
    "AgentSignal",
    "SignalSource",
    "Action",
    "WeightConfig",
    "HistoricalAccuracyTracker",
    "DynamicWeightAdjuster",
    "ConflictResolver",
    "get_ensemble",
    "ensemble_decision",
    "create_agent_signal",
    
    # Practice
    "MiroFishPractice",
    "PracticeSession",
    "PracticeTrade",
    "MiroFishConfig",
    "TradeStatus",
    "TradeDirection",
    "ExitReason",
    "get_practice",
    "create_practice_session",
    "evaluate_trade_entry",
    "simulate_trade",
    "close_trade",
    "get_session_results",
    "get_available_configs",
    "DEFAULT_CONFIGS",
]
