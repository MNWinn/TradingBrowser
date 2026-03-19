"""
Research Scheduler for TradingBrowser.

Provides Celery-based scheduling for analysis tasks:
- Cron-like scheduling for periodic analysis
- Priority queue management for hot tickers
- Batch processing capabilities
- Resource management and throttling
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as redis
from celery import chain, chord, group
from celery.schedules import crontab

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    """Types of scheduled tasks."""
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"


class AnalysisType(str, Enum):
    """Types of analysis tasks."""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    SWARM = "swarm"
    FULL_RESEARCH = "full_research"


@dataclass
class ScheduledTask:
    """Represents a scheduled analysis task."""
    task_id: str
    name: str
    schedule_type: ScheduleType
    analysis_type: AnalysisType
    tickers: list[str]
    schedule_config: dict  # cron expression or interval seconds
    priority: int = 5
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "analysis_type": self.analysis_type.value,
            "tickers": self.tickers,
            "schedule_config": self.schedule_config,
            "priority": self.priority,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            analysis_type=AnalysisType(data["analysis_type"]),
            tickers=data["tickers"],
            schedule_config=data["schedule_config"],
            priority=data.get("priority", 5),
            enabled=data.get("enabled", True),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            run_count=data.get("run_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
        )


@dataclass
class HotTicker:
    """Represents a hot ticker requiring priority analysis."""
    ticker: str
    priority_score: float  # 0-100
    reasons: list[str]
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_count: int = 0
    last_analysis: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "priority_score": self.priority_score,
            "reasons": self.reasons,
            "added_at": self.added_at.isoformat(),
            "analysis_count": self.analysis_count,
            "last_analysis": self.last_analysis.isoformat() if self.last_analysis else None,
        }


class ResearchScheduler:
    """
    Research scheduling system with Celery integration.
    
    Features:
    - Cron-like scheduling for periodic analysis
    - Priority queue for hot tickers
    - Batch processing with resource management
    - Throttling and rate limiting
    """
    
    # Redis key prefixes
    SCHEDULED_TASKS_KEY = "scheduler:tasks"
    HOT_TICKERS_KEY = "scheduler:hot_tickers"
    HOT_TICKERS_QUEUE = "scheduler:hot_queue"
    BATCH_QUEUE_KEY = "scheduler:batch_queue"
    RESOURCE_USAGE_KEY = "scheduler:resource_usage"
    SCHEDULER_METRICS_KEY = "scheduler:metrics"
    
    # Configuration
    MAX_CONCURRENT_ANALYSES = 5
    BATCH_SIZE = 10
    RATE_LIMIT_PER_MINUTE = 60
    HOT_TICKER_THRESHOLD = 70.0
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._scheduled_tasks: dict[str, ScheduledTask] = {}
        self._hot_tickers: dict[str, HotTicker] = {}
        self._resource_usage: dict[str, list[float]] = defaultdict(list)
        
    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def initialize(self) -> None:
        """Initialize the research scheduler."""
        await self.redis.ping()
        await self._load_scheduled_tasks()
        await self._load_hot_tickers()
        logger.info("ResearchScheduler initialized")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the scheduler."""
        await self._save_scheduled_tasks()
        await self._save_hot_tickers()
        logger.info("ResearchScheduler shutdown complete")
    
    async def schedule_cron_task(
        self,
        name: str,
        analysis_type: AnalysisType,
        tickers: list[str],
        cron_expression: dict,  # {"minute": "0", "hour": "9", "day_of_week": "mon-fri"}
        priority: int = 5,
    ) -> ScheduledTask:
        """
        Schedule a recurring task with cron-like timing.
        
        Args:
            name: Task name
            analysis_type: Type of analysis to run
            tickers: List of tickers to analyze
            cron_expression: Dict with minute, hour, day_of_week, etc.
            priority: Task priority (1-10)
        """
        import uuid
        
        task = ScheduledTask(
            task_id=f"sched-{uuid.uuid4().hex[:12]}",
            name=name,
            schedule_type=ScheduleType.CRON,
            analysis_type=analysis_type,
            tickers=tickers,
            schedule_config=cron_expression,
            priority=priority,
        )
        
        # Calculate next run time
        task.next_run = self._calculate_next_run(task)
        
        self._scheduled_tasks[task.task_id] = task
        await self._save_task(task)
        
        # Register with Celery beat (if configured)
        await self._register_celery_beat_task(task)
        
        logger.info(f"Scheduled cron task '{name}' for {analysis_type.value} analysis")
        return task
    
    async def schedule_interval_task(
        self,
        name: str,
        analysis_type: AnalysisType,
        tickers: list[str],
        interval_seconds: int,
        priority: int = 5,
    ) -> ScheduledTask:
        """
        Schedule a recurring task with fixed interval.
        
        Args:
            name: Task name
            analysis_type: Type of analysis to run
            tickers: List of tickers to analyze
            interval_seconds: Seconds between runs
            priority: Task priority (1-10)
        """
        import uuid
        
        task = ScheduledTask(
            task_id=f"sched-{uuid.uuid4().hex[:12]}",
            name=name,
            schedule_type=ScheduleType.INTERVAL,
            analysis_type=analysis_type,
            tickers=tickers,
            schedule_config={"interval_seconds": interval_seconds},
            priority=priority,
        )
        
        task.next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        
        self._scheduled_tasks[task.task_id] = task
        await self._save_task(task)
        
        logger.info(f"Scheduled interval task '{name}' every {interval_seconds}s")
        return task
    
    async def add_hot_ticker(
        self,
        ticker: str,
        priority_score: float,
        reasons: list[str],
    ) -> HotTicker:
        """
        Add a ticker to the hot tickers priority queue.
        
        Args:
            ticker: Stock ticker symbol
            priority_score: Priority score (0-100)
            reasons: List of reasons for priority status
        """
        ticker = ticker.upper()
        
        hot_ticker = HotTicker(
            ticker=ticker,
            priority_score=min(max(priority_score, 0), 100),
            reasons=reasons,
        )
        
        self._hot_tickers[ticker] = hot_ticker
        
        # Add to priority queue (score = 100 - priority for ascending sort)
        queue_score = 100 - priority_score
        await self.redis.zadd(self.HOT_TICKERS_QUEUE, {ticker: queue_score})
        await self.redis.setex(
            f"{self.HOT_TICKERS_KEY}:{ticker}",
            86400,  # 24 hour TTL
            json.dumps(hot_ticker.to_dict())
        )
        
        logger.info(f"Added {ticker} to hot tickers (score: {priority_score})")
        return hot_ticker
    
    async def remove_hot_ticker(self, ticker: str) -> bool:
        """Remove a ticker from the hot tickers queue."""
        ticker = ticker.upper()
        
        if ticker in self._hot_tickers:
            del self._hot_tickers[ticker]
            await self.redis.zrem(self.HOT_TICKERS_QUEUE, ticker)
            await self.redis.delete(f"{self.HOT_TICKERS_KEY}:{ticker}")
            logger.info(f"Removed {ticker} from hot tickers")
            return True
        return False
    
    async def get_hot_tickers(self, limit: int = 50) -> list[HotTicker]:
        """Get hot tickers sorted by priority."""
        tickers = await self.redis.zrange(self.HOT_TICKERS_QUEUE, 0, limit - 1)
        result = []
        
        for ticker in tickers:
            data = await self.redis.get(f"{self.HOT_TICKERS_KEY}:{ticker}")
            if data:
                result.append(HotTicker.from_dict(json.loads(data)))
        
        return result
    
    async def process_hot_tickers_batch(self, batch_size: int = 10) -> list[dict]:
        """
        Process a batch of hot tickers.
        
        Returns:
            List of analysis results
        """
        # Get highest priority tickers
        hot_tickers = await self.get_hot_tickers(batch_size)
        
        if not hot_tickers:
            return []
        
        results = []
        for hot_ticker in hot_tickers:
            try:
                # Check rate limiting
                if not await self._check_rate_limit():
                    logger.warning("Rate limit reached, pausing batch processing")
                    break
                
                # Trigger analysis
                result = await self._trigger_analysis(
                    ticker=hot_ticker.ticker,
                    analysis_type=AnalysisType.SWARM,
                    priority=1,  # High priority for hot tickers
                )
                
                # Update hot ticker stats
                hot_ticker.analysis_count += 1
                hot_ticker.last_analysis = datetime.now(timezone.utc)
                await self.redis.setex(
                    f"{self.HOT_TICKERS_KEY}:{hot_ticker.ticker}",
                    86400,
                    json.dumps(hot_ticker.to_dict())
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing hot ticker {hot_ticker.ticker}: {e}")
        
        return results
    
    async def create_batch_job(
        self,
        tickers: list[str],
        analysis_type: AnalysisType,
        priority: int = 5,
    ) -> str:
        """
        Create a batch analysis job.
        
        Args:
            tickers: List of tickers to analyze
            analysis_type: Type of analysis
            priority: Job priority
            
        Returns:
            Batch job ID
        """
        import uuid
        
        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        
        # Split into chunks for processing
        chunks = [tickers[i:i + self.BATCH_SIZE] for i in range(0, len(tickers), self.BATCH_SIZE)]
        
        batch_data = {
            "batch_id": batch_id,
            "analysis_type": analysis_type.value,
            "priority": priority,
            "total_tickers": len(tickers),
            "chunks": len(chunks),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued",
        }
        
        await self.redis.setex(
            f"{self.BATCH_QUEUE_KEY}:{batch_id}",
            86400,
            json.dumps(batch_data)
        )
        
        # Queue chunks
        for i, chunk in enumerate(chunks):
            await self.redis.lpush(
                f"{self.BATCH_QUEUE_KEY}:{batch_id}:chunks",
                json.dumps({"chunk_index": i, "tickers": chunk})
            )
        
        logger.info(f"Created batch job {batch_id} for {len(tickers)} tickers")
        return batch_id
    
    async def get_batch_status(self, batch_id: str) -> Optional[dict]:
        """Get the status of a batch job."""
        data = await self.redis.get(f"{self.BATCH_QUEUE_KEY}:{batch_id}")
        if data:
            status = json.loads(data)
            # Get progress
            chunks_remaining = await self.redis.llen(f"{self.BATCH_QUEUE_KEY}:{batch_id}:chunks")
            status["chunks_remaining"] = chunks_remaining
            return status
        return None
    
    async def check_resources(self) -> dict:
        """Check current resource usage."""
        # Get Celery worker stats
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        
        total_active = sum(len(t) for t in active_tasks.values())
        total_scheduled = sum(len(t) for t in scheduled_tasks.values())
        total_reserved = sum(len(t) for t in reserved_tasks.values())
        
        # Get queue depths from Redis
        pipeline_queue = await self.redis.zcard("research:job_queue")
        hot_queue = await self.redis.zcard(self.HOT_TICKERS_QUEUE)
        
        return {
            "celery": {
                "active_tasks": total_active,
                "scheduled_tasks": total_scheduled,
                "reserved_tasks": total_reserved,
            },
            "queues": {
                "pipeline": pipeline_queue,
                "hot_tickers": hot_queue,
            },
            "capacity": {
                "max_concurrent": self.MAX_CONCURRENT_ANALYSES,
                "available_slots": max(0, self.MAX_CONCURRENT_ANALYSES - total_active),
            },
        }
    
    async def get_scheduled_tasks(self) -> list[dict]:
        """Get all scheduled tasks."""
        return [task.to_dict() for task in self._scheduled_tasks.values()]
    
    async def enable_task(self, task_id: str) -> bool:
        """Enable a scheduled task."""
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id].enabled = True
            await self._save_task(self._scheduled_tasks[task_id])
            return True
        return False
    
    async def disable_task(self, task_id: str) -> bool:
        """Disable a scheduled task."""
        if task_id in self._scheduled_tasks:
            self._scheduled_tasks[task_id].enabled = False
            await self._save_task(self._scheduled_tasks[task_id])
            return True
        return False
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a scheduled task."""
        if task_id in self._scheduled_tasks:
            del self._scheduled_tasks[task_id]
            await self.redis.hdel(self.SCHEDULED_TASKS_KEY, task_id)
            return True
        return False
    
    async def _calculate_next_run(self, task: ScheduledTask) -> Optional[datetime]:
        """Calculate the next run time for a scheduled task."""
        now = datetime.now(timezone.utc)
        
        if task.schedule_type == ScheduleType.INTERVAL:
            interval = task.schedule_config.get("interval_seconds", 3600)
            return now + timedelta(seconds=interval)
        
        elif task.schedule_type == ScheduleType.CRON:
            # Simplified cron calculation - in production use croniter
            # For now, assume daily at specified time
            hour = int(task.schedule_config.get("hour", 0))
            minute = int(task.schedule_config.get("minute", 0))
            
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        return None
    
    async def _register_celery_beat_task(self, task: ScheduledTask) -> None:
        """Register task with Celery beat schedule."""
        # This would dynamically add to Celery beat schedule
        # For now, tasks are managed internally
        pass
    
    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old entries
        self._resource_usage["requests"] = [
            t for t in self._resource_usage["requests"] if t > minute_ago
        ]
        
        # Check limit
        if len(self._resource_usage["requests"]) >= self.RATE_LIMIT_PER_MINUTE:
            return False
        
        # Record request
        self._resource_usage["requests"].append(now)
        return True
    
    async def _trigger_analysis(
        self,
        ticker: str,
        analysis_type: AnalysisType,
        priority: int = 5,
    ) -> dict:
        """Trigger an analysis task."""
        # Import here to avoid circular imports
        from app.services.research_pipeline.pipeline_orchestrator import (
            get_orchestrator,
            ResearchTriggerType,
        )
        
        orchestrator = await get_orchestrator()
        
        job = await orchestrator.submit_job(
            ticker=ticker,
            trigger_type=ResearchTriggerType.SCHEDULED,
            priority=priority,
            payload={"analysis_type": analysis_type.value},
        )
        
        return {
            "job_id": job.job_id,
            "ticker": ticker,
            "analysis_type": analysis_type.value,
            "status": job.status.value,
        }
    
    async def _save_task(self, task: ScheduledTask) -> None:
        """Save a scheduled task to Redis."""
        await self.redis.hset(
            self.SCHEDULED_TASKS_KEY,
            task.task_id,
            json.dumps(task.to_dict())
        )
    
    async def _load_scheduled_tasks(self) -> None:
        """Load scheduled tasks from Redis."""
        tasks_data = await self.redis.hgetall(self.SCHEDULED_TASKS_KEY)
        for task_id, task_json in tasks_data.items():
            try:
                task = ScheduledTask.from_dict(json.loads(task_json))
                self._scheduled_tasks[task_id] = task
            except Exception as e:
                logger.error(f"Error loading scheduled task {task_id}: {e}")
    
    async def _save_scheduled_tasks(self) -> None:
        """Save all scheduled tasks to Redis."""
        for task in self._scheduled_tasks.values():
            await self._save_task(task)
    
    async def _load_hot_tickers(self) -> None:
        """Load hot tickers from Redis."""
        tickers = await self.redis.zrange(self.HOT_TICKERS_QUEUE, 0, -1)
        for ticker in tickers:
            data = await self.redis.get(f"{self.HOT_TICKERS_KEY}:{ticker}")
            if data:
                try:
                    hot_ticker = HotTicker.from_dict(json.loads(data))
                    self._hot_tickers[ticker] = hot_ticker
                except Exception as e:
                    logger.error(f"Error loading hot ticker {ticker}: {e}")
    
    async def _save_hot_tickers(self) -> None:
        """Save hot tickers to Redis."""
        for ticker, hot_ticker in self._hot_tickers.items():
            await self.redis.setex(
                f"{self.HOT_TICKERS_KEY}:{ticker}",
                86400,
                json.dumps(hot_ticker.to_dict())
            )


# Celery tasks for the scheduler

@celery_app.task(bind=True, max_retries=3)
def run_research_analysis(
    self,
    job_id: str,
    ticker: str,
    trigger_type: str,
    payload: dict,
) -> dict:
    """
    Run research analysis as a Celery task.
    
    This is the main entry point for research jobs from the pipeline.
    """
    import asyncio
    
    logger.info(f"Running research analysis for {ticker} (job: {job_id})")
    
    try:
        # Run the swarm analysis
        result = asyncio.run(_execute_swarm_analysis(ticker, payload))
        
        return {
            "job_id": job_id,
            "ticker": ticker,
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
def process_scheduled_analysis(task_id: str) -> dict:
    """Process a scheduled analysis task."""
    logger.info(f"Processing scheduled analysis task: {task_id}")
    
    # This would load the task config and execute
    return {"task_id": task_id, "status": "processed"}


@celery_app.task
def process_hot_ticker_batch() -> dict:
    """Process a batch of hot tickers."""
    import asyncio
    
    async def _process():
        scheduler = ResearchScheduler()
        await scheduler.initialize()
        results = await scheduler.process_hot_tickers_batch()
        await scheduler.shutdown()
        return results
    
    return asyncio.run(_process())


# Global scheduler instance
_scheduler: Optional[ResearchScheduler] = None


async def get_scheduler() -> ResearchScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ResearchScheduler()
        await _scheduler.initialize()
    return _scheduler


async def shutdown_scheduler() -> None:
    """Shutdown the global scheduler."""
    global _scheduler
    if _scheduler:
        await _scheduler.shutdown()
        _scheduler = None
