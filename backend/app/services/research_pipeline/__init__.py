"""
Continuous Market Research Pipeline for TradingBrowser.

This package provides a comprehensive research pipeline with:
- 24/7 market monitoring
- Scheduled analysis jobs
- Event-driven research triggers
- Signal routing and distribution
- Comprehensive logging and monitoring

Usage:
    from app.services.research_pipeline import (
        get_orchestrator,
        get_market_watch,
        get_scheduler,
        get_router,
    )
    
    # Initialize components
    orchestrator = await get_orchestrator()
    market_watch = await get_market_watch()
    scheduler = await get_scheduler()
    router = await get_router()
"""

from .pipeline_orchestrator import (
    PipelineOrchestrator,
    ResearchJob,
    ResearchJobStatus,
    ResearchTriggerType,
    get_orchestrator,
    shutdown_orchestrator,
)

from .market_watch import (
    MarketWatch,
    MarketAlert,
    PriceAlert,
    VolumeAlert,
    AlertType,
    AlertSeverity,
    get_market_watch,
    shutdown_market_watch,
)

from .research_scheduler import (
    ResearchScheduler,
    ScheduledTask,
    HotTicker,
    ScheduleType,
    AnalysisType,
    run_research_analysis,
    get_scheduler,
    shutdown_scheduler,
)

from .signal_router import (
    SignalRouter,
    Signal,
    RoutingRule,
    SignalType,
    SignalPriority,
    AgentType,
    get_router,
    shutdown_router,
    route_buy_signal,
    route_sell_signal,
    route_alert,
)

__all__ = [
    # Pipeline Orchestrator
    "PipelineOrchestrator",
    "ResearchJob",
    "ResearchJobStatus",
    "ResearchTriggerType",
    "get_orchestrator",
    "shutdown_orchestrator",
    
    # Market Watch
    "MarketWatch",
    "MarketAlert",
    "PriceAlert",
    "VolumeAlert",
    "AlertType",
    "AlertSeverity",
    "get_market_watch",
    "shutdown_market_watch",
    
    # Research Scheduler
    "ResearchScheduler",
    "ScheduledTask",
    "HotTicker",
    "ScheduleType",
    "AnalysisType",
    "run_research_analysis",
    "get_scheduler",
    "shutdown_scheduler",
    
    # Signal Router
    "SignalRouter",
    "Signal",
    "RoutingRule",
    "SignalType",
    "SignalPriority",
    "AgentType",
    "get_router",
    "shutdown_router",
    "route_buy_signal",
    "route_sell_signal",
    "route_alert",
]


async def initialize_pipeline() -> dict:
    """
    Initialize the complete research pipeline.
    
    Returns:
        Dictionary with initialized components
    """
    orchestrator = await get_orchestrator()
    market_watch = await get_market_watch()
    scheduler = await get_scheduler()
    router = await get_router()
    
    return {
        "orchestrator": orchestrator,
        "market_watch": market_watch,
        "scheduler": scheduler,
        "router": router,
    }


async def shutdown_pipeline() -> None:
    """Shutdown all pipeline components gracefully."""
    await shutdown_orchestrator()
    await shutdown_market_watch()
    await shutdown_scheduler()
    await shutdown_router()
