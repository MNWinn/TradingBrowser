import asyncio
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.services.evaluation import run_daily_recalibration
from app.workers.celery_app import celery_app


@celery_app.task
def run_daily_training():
    db = SessionLocal()
    try:
        metrics = run_daily_recalibration(db)
        return {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Recalibrated ensemble weights and updated soft risk heuristics.",
            "metrics": metrics,
        }
    finally:
        db.close()


# ============================================================================
# Research Pipeline Celery Tasks
# ============================================================================

@celery_app.task(bind=True, max_retries=3)
def run_research_analysis_task(self, job_id: str, ticker: str, trigger_type: str, payload: dict):
    """
    Run research analysis as a Celery task.
    
    Args:
        job_id: Unique job identifier
        ticker: Stock ticker symbol
        trigger_type: What triggered this research
        payload: Additional job data
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[Celery] Running research analysis for {ticker} (job: {job_id})")
    
    try:
        # Run the swarm analysis
        result = asyncio.run(_execute_swarm_analysis(ticker, payload))
        
        return {
            "job_id": job_id,
            "ticker": ticker,
            "trigger_type": trigger_type,
            "status": "completed",
            "result": result,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        
    except Exception as exc:
        logger.exception(f"Research analysis failed for {ticker}: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        
        return {
            "job_id": job_id,
            "ticker": ticker,
            "trigger_type": trigger_type,
            "status": "failed",
            "error": str(exc),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }


async def _execute_swarm_analysis(ticker: str, payload: dict) -> dict:
    """Execute swarm analysis for a ticker."""
    from app.services.swarm import SwarmOrchestrator
    
    orchestrator = SwarmOrchestrator()
    result = await orchestrator.run(ticker=ticker, mode=payload.get("mode", "research"))
    
    return result


@celery_app.task
def process_hot_ticker_batch_task(batch_size: int = 10) -> dict:
    """Process a batch of hot tickers."""
    from app.services.research_pipeline.research_scheduler import ResearchScheduler
    
    async def _process():
        scheduler = ResearchScheduler()
        await scheduler.initialize()
        results = await scheduler.process_hot_tickers_batch(batch_size)
        await scheduler.shutdown()
        return results
    
    return asyncio.run(_process())


@celery_app.task
def process_scheduled_analysis_task(task_id: str) -> dict:
    """Process a scheduled analysis task."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Processing scheduled analysis task: {task_id}")
    
    # This would load the task config and execute
    return {
        "task_id": task_id,
        "status": "processed",
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task
def check_market_alerts_task() -> dict:
    """Check market alerts and trigger notifications."""
    from app.services.research_pipeline.market_watch import get_market_watch
    
    async def _check():
        market_watch = await get_market_watch()
        # The market watch runs continuously, but this task can be used
        # for additional periodic checks or health monitoring
        alerts = await market_watch.get_alert_history(limit=50)
        return {
            "alerts_checked": len(alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    return asyncio.run(_check())


@celery_app.task
def cleanup_old_data_task() -> dict:
    """Clean up old pipeline data."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Running pipeline data cleanup")
    
    # This would clean up old jobs, signals, logs, etc.
    return {
        "status": "completed",
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task
def generate_pipeline_report_task() -> dict:
    """Generate a pipeline health and metrics report."""
    from app.services.research_pipeline.monitoring import get_monitor
    
    async def _generate():
        monitor = await get_monitor()
        dashboard_data = await monitor.get_dashboard_data()
        return {
            "report_type": "pipeline_health",
            "data": dashboard_data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    return asyncio.run(_generate())
