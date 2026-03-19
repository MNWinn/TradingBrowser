"""
MiroFish Advanced Integration Layer

This package provides advanced MiroFish integration capabilities:

- **mirofish_fleet**: Multi-timeframe, multi-lens assessment management
- **mirofish_cache**: Redis-based caching with TTL management
- **mirofish_ensemble**: Ensemble decision making with other agents
- **mirofish_practice**: Paper trading practice mode
- **mirofish_explainer**: Prediction explainability and breakdown
- **mirofish_scenarios**: Scenario analysis and what-if simulations
- **mirofish_backtest**: Historical backtesting of signals
- **mirofish_comparison**: Compare signals with other sources

Usage:
    from app.services.mirofish import (
        get_fleet,
        get_cache,
        get_ensemble,
        get_practice,
        get_explainer,
        get_scenario_analyzer,
        get_backtester,
        get_comparator,
        fleet_analyze,
        cached_assessment,
        ensemble_decision,
        explain_prediction,
        analyze_scenarios,
        run_backtest,
        compare_signals,
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

# New Deep Dive modules
from app.services.mirofish.mirofish_explainer import (
    PredictionExplainer,
    PredictionExplanation,
    FactorComponent,
    ContradictingSignal,
    FactorType,
    SignalStrength,
    MiroFishExplanation,
    MiroFishExplanationHistory,
    get_explainer,
    explain_prediction,
    get_explanation,
)

from app.services.mirofish.mirofish_scenarios import (
    ScenarioAnalyzer,
    ScenarioAnalysis,
    ScenarioOutcome,
    RiskRewardAnalysis,
    ProbabilityDistribution,
    ScenarioType,
    OutcomeLikelihood,
    MiroFishScenario,
    get_scenario_analyzer,
    analyze_scenarios,
    run_monte_carlo,
)

from app.services.mirofish.mirofish_backtest import (
    MiroFishBacktester,
    BacktestResult,
    BacktestTrade,
    TradeDirection as BacktestTradeDirection,
    TradeStatus as BacktestTradeStatus,
    MiroFishBacktest,
    MiroFishBacktestConfig,
    get_backtester,
    run_backtest,
    optimize_parameters,
    walk_forward_analysis,
)

from app.services.mirofish.mirofish_comparison import (
    SignalComparator,
    ComprehensiveComparison,
    SignalComparison,
    SourceAccuracy,
    SignalSourceType,
    AgreementLevel,
    MiroFishComparison,
    MiroFishAccuracyTracking,
    get_comparator,
    compare_signals,
    get_accuracy_ranking,
    record_prediction_outcome,
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
    
    # Explainer
    "PredictionExplainer",
    "PredictionExplanation",
    "FactorComponent",
    "ContradictingSignal",
    "FactorType",
    "SignalStrength",
    "MiroFishExplanation",
    "MiroFishExplanationHistory",
    "get_explainer",
    "explain_prediction",
    "get_explanation",
    
    # Scenarios
    "ScenarioAnalyzer",
    "ScenarioAnalysis",
    "ScenarioOutcome",
    "RiskRewardAnalysis",
    "ProbabilityDistribution",
    "ScenarioType",
    "OutcomeLikelihood",
    "MiroFishScenario",
    "get_scenario_analyzer",
    "analyze_scenarios",
    "run_monte_carlo",
    
    # Backtest
    "MiroFishBacktester",
    "BacktestResult",
    "BacktestTrade",
    "BacktestTradeDirection",
    "BacktestTradeStatus",
    "MiroFishBacktest",
    "MiroFishBacktestConfig",
    "get_backtester",
    "run_backtest",
    "optimize_parameters",
    "walk_forward_analysis",
    
    # Comparison
    "SignalComparator",
    "ComprehensiveComparison",
    "SignalComparison",
    "SourceAccuracy",
    "SignalSourceType",
    "AgreementLevel",
    "MiroFishComparison",
    "MiroFishAccuracyTracking",
    "get_comparator",
    "compare_signals",
    "get_accuracy_ranking",
    "record_prediction_outcome",
]

# Analytics
from app.services.mirofish.analytics import (
    MiroFishAnalytics,
    AccuracyMetrics,
    PerformanceMetrics,
    TimeSeriesAnalysis,
    VisualizationData,
    get_analytics,
    store_prediction,
    record_outcome,
    get_overall_accuracy,
    get_ticker_accuracy,
    get_timeframe_accuracy,
    get_time_series_analysis,
    get_performance_metrics,
    get_signal_type_performance,
    get_visualization_data,
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
    
    # Explainer
    "PredictionExplainer",
    "PredictionExplanation",
    "FactorComponent",
    "ContradictingSignal",
    "FactorType",
    "SignalStrength",
    "MiroFishExplanation",
    "MiroFishExplanationHistory",
    "get_explainer",
    "explain_prediction",
    "get_explanation",
    
    # Scenarios
    "ScenarioAnalyzer",
    "ScenarioAnalysis",
    "ScenarioOutcome",
    "RiskRewardAnalysis",
    "ProbabilityDistribution",
    "ScenarioType",
    "OutcomeLikelihood",
    "MiroFishScenario",
    "get_scenario_analyzer",
    "analyze_scenarios",
    "run_monte_carlo",
    
    # Backtest
    "MiroFishBacktester",
    "BacktestResult",
    "BacktestTrade",
    "BacktestTradeDirection",
    "BacktestTradeStatus",
    "MiroFishBacktest",
    "MiroFishBacktestConfig",
    "get_backtester",
    "run_backtest",
    "optimize_parameters",
    "walk_forward_analysis",
    
    # Comparison
    "SignalComparator",
    "ComprehensiveComparison",
    "SignalComparison",
    "SourceAccuracy",
    "SignalSourceType",
    "AgreementLevel",
    "MiroFishComparison",
    "MiroFishAccuracyTracking",
    "get_comparator",
    "compare_signals",
    "get_accuracy_ranking",
    "record_prediction_outcome",
    
    # Analytics
    "MiroFishAnalytics",
    "AccuracyMetrics",
    "PerformanceMetrics",
    "TimeSeriesAnalysis",
    "VisualizationData",
    "get_analytics",
    "store_prediction",
    "record_outcome",
    "get_overall_accuracy",
    "get_ticker_accuracy",
    "get_timeframe_accuracy",
    "get_time_series_analysis",
    "get_performance_metrics",
    "get_signal_type_performance",
    "get_visualization_data",
]
