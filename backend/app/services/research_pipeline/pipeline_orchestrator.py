"""
Continuous Market Research Pipeline for TradingBrowser.

This module provides 24/7 market monitoring, scheduled analysis jobs,
event-driven research triggers, and research queue management.
"""

import asyncio
import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as redis
from celery import chain, group

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class ResearchJobStatus(str, Enum):
    """Research job lifecycle states."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResearchTriggerType(str, Enum):
    """Types of research triggers."""
    SCHEDULED = "scheduled"
    PRICE_ALERT = "price_alert"
    VOLUME_SPIKE = "volume_spike"
    NEWS_EVENT = "news_event"
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    MANUAL = "manual"
    SYSTEM = "system"


@dataclass
class ResearchJob:
    """Represents a research job in the pipeline."""
    job_id: str
    ticker: str
    trigger_type: ResearchTriggerType
    priority: int = 5  # 1-10, lower is higher priority
    status: ResearchJobStatus = ResearchJobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    payload: dict = field(default_factory=dict)
    result: Optional[dict] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "ticker": self.ticker,
            "trigger_type": self.trigger_type.value,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "payload": self.payload,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ResearchJob":
        return cls(
            job_id=data["job_id"],
            ticker=data["ticker"],
            trigger_type=ResearchTriggerType(data.get("trigger_type", "manual")),
            priority=data.get("priority", 5),
            status=ResearchJobStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            payload=data.get("payload", {}),
            result=data.get("result"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )


class PipelineOrchestrator:
    """
    Central orchestrator for continuous market research.
    
    Responsibilities:
    - 24/7 market monitoring coordination
    - Research job queue management
    - Event-driven research trigger handling
    - Integration with Celery for background processing
    - Research pipeline health monitoring
    """
    
    # Redis key prefixes
    JOB_QUEUE_KEY = "research:job_queue"
    JOB_DATA_PREFIX = "research:job:{job_id}"
    ACTIVE_JOBS_KEY = "research:active_jobs"
    COMPLETED_JOBS_KEY = "research:completed_jobs"
    FAILED_JOBS_KEY = "research:failed_jobs"
    PIPELINE_METRICS_KEY = "research:metrics"
    PIPELINE_STATE_KEY = "research:pipeline_state"
    
    # Configuration
    MAX_CONCURRENT_JOBS = 10
    JOB_TIMEOUT_SECONDS = 300
    METRICS_RETENTION_HOURS = 24
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._job_processor_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._subscribers: list[Callable[[dict], Coroutine]] = []
        self._active_jobs: dict[str, ResearchJob] = {}
        self._job_history: deque = deque(maxlen=1000)
        
    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def initialize(self) -> None:
        """Initialize the pipeline orchestrator."""
        await self.redis.ping()
        self._running = True
        
        # Start background tasks
        self._job_processor_task = asyncio.create_task(self._process_job_queue())
        self._metrics_task = asyncio.create_task(self._metrics_collection_loop())
        
        # Restore any pending jobs from Redis
        await self._restore_pending_jobs()
        
        await self._update_pipeline_state("initialized")
        logger.info("PipelineOrchestrator initialized and ready for 24/7 monitoring")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the pipeline orchestrator."""
        self._running = False
        self._shutdown_event.set()
        
        # Cancel background tasks
        for task in [self._job_processor_task, self._metrics_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Save active jobs state
        for job in self._active_jobs.values():
            await self._save_job(job)
        
        await self._update_pipeline_state("shutdown")
        logger.info("PipelineOrchestrator shutdown complete")
    
    async def submit_job(
        self,
        ticker: str,
        trigger_type: ResearchTriggerType,
        priority: int = 5,
        payload: Optional[dict] = None,
    ) -> ResearchJob:
        """
        Submit a new research job to the pipeline.
        
        Args:
            ticker: Stock ticker symbol
            trigger_type: What triggered this research
            priority: Job priority (1-10, lower is higher)
            payload: Additional job data
            
        Returns:
            The created ResearchJob
        """
        job = ResearchJob(
            job_id=f"research-{uuid.uuid4().hex[:12]}",
            ticker=ticker.upper(),
            trigger_type=trigger_type,
            priority=priority,
            payload=payload or {},
        )
        
        # Save job data
        await self._save_job(job)
        
        # Add to priority queue (score = priority * 1000000 + timestamp for FIFO within same priority)
        score = priority * 1000000000000 + int(datetime.now(timezone.utc).timestamp())
        await self.redis.zadd(self.JOB_QUEUE_KEY, {job.job_id: score})
        
        job.status = ResearchJobStatus.QUEUED
        await self._save_job(job)
        
        # Publish job queued event
        await self._publish_event("job_queued", job.to_dict())
        
        logger.info(f"Research job {job.job_id} submitted for {ticker} (priority: {priority})")
        return job
    
    async def submit_batch_jobs(
        self,
        tickers: list[str],
        trigger_type: ResearchTriggerType,
        priority: int = 5,
        payload: Optional[dict] = None,
    ) -> list[ResearchJob]:
        """Submit multiple research jobs as a batch."""
        jobs = []
        for ticker in tickers:
            job = await self.submit_job(ticker, trigger_type, priority, payload)
            jobs.append(job)
        return jobs
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or queued job."""
        job_data = await self.redis.get(self.JOB_DATA_PREFIX.format(job_id=job_id))
        if not job_data:
            return False
        
        job = ResearchJob.from_dict(json.loads(job_data))
        
        if job.status in [ResearchJobStatus.PENDING, ResearchJobStatus.QUEUED]:
            job.status = ResearchJobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            await self._save_job(job)
            await self.redis.zrem(self.JOB_QUEUE_KEY, job_id)
            await self._publish_event("job_cancelled", job.to_dict())
            logger.info(f"Research job {job_id} cancelled")
            return True
        
        return False
    
    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get the current status of a job."""
        job_data = await self.redis.get(self.JOB_DATA_PREFIX.format(job_id=job_id))
        if job_data:
            return json.loads(job_data)
        return None
    
    async def get_queue_stats(self) -> dict:
        """Get current queue statistics."""
        queue_length = await self.redis.zcard(self.JOB_QUEUE_KEY)
        active_count = len(self._active_jobs)
        
        # Get priority distribution
        queue_items = await self.redis.zrange(self.JOB_QUEUE_KEY, 0, -1, withscores=True)
        priority_dist = {}
        for _, score in queue_items:
            priority = int(score) // 1000000000000
            priority_dist[priority] = priority_dist.get(priority, 0) + 1
        
        return {
            "queue_length": queue_length,
            "active_jobs": active_count,
            "priority_distribution": priority_dist,
            "max_concurrent": self.MAX_CONCURRENT_JOBS,
            "available_slots": self.MAX_CONCURRENT_JOBS - active_count,
        }
    
    async def get_pipeline_metrics(self) -> dict:
        """Get comprehensive pipeline metrics."""
        metrics_data = await self.redis.get(self.PIPELINE_METRICS_KEY)
        if metrics_data:
            return json.loads(metrics_data)
        return self._get_default_metrics()
    
    async def subscribe(self, callback: Callable[[dict], Coroutine]) -> None:
        """Subscribe to pipeline events."""
        self._subscribers.append(callback)
    
    async def unsubscribe(self, callback: Callable[[dict], Coroutine]) -> None:
        """Unsubscribe from pipeline events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def _process_job_queue(self) -> None:
        """Background task to process jobs from the queue."""
        while self._running:
            try:
                # Check if we can process more jobs
                if len(self._active_jobs) >= self.MAX_CONCURRENT_JOBS:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get highest priority job from queue
                job_ids = await self.redis.zrange(self.JOB_QUEUE_KEY, 0, 0)
                if not job_ids:
                    await asyncio.sleep(0.5)
                    continue
                
                job_id = job_ids[0]
                
                # Remove from queue and process
                removed = await self.redis.zrem(self.JOB_QUEUE_KEY, job_id)
                if removed:
                    await self._execute_job(job_id)
                
            except Exception as e:
                logger.exception(f"Error processing job queue: {e}")
                await asyncio.sleep(1)
    
    async def _execute_job(self, job_id: str) -> None:
        """Execute a research job."""
        job_data = await self.redis.get(self.JOB_DATA_PREFIX.format(job_id=job_id))
        if not job_data:
            logger.warning(f"Job {job_id} not found in Redis")
            return
        
        job = ResearchJob.from_dict(json.loads(job_data))
        
        try:
            job.status = ResearchJobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            self._active_jobs[job_id] = job
            await self._save_job(job)
            
            await self._publish_event("job_started", job.to_dict())
            
            # Dispatch to Celery task
            result = await self._dispatch_celery_task(job)
            
            job.status = ResearchJobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            
            await self.redis.sadd(self.COMPLETED_JOBS_KEY, job_id)
            await self._update_metrics("completed", job)
            await self._publish_event("job_completed", job.to_dict())
            
            logger.info(f"Research job {job_id} completed successfully")
            
        except Exception as e:
            logger.exception(f"Research job {job_id} failed: {e}")
            
            job.retry_count += 1
            if job.retry_count < job.max_retries:
                # Re-queue for retry
                job.status = ResearchJobStatus.QUEUED
                job.error_message = str(e)
                score = job.priority * 1000000000000 + int(datetime.now(timezone.utc).timestamp())
                await self.redis.zadd(self.JOB_QUEUE_KEY, {job_id: score})
                await self._publish_event("job_retry", job.to_dict())
            else:
                job.status = ResearchJobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                await self.redis.sadd(self.FAILED_JOBS_KEY, job_id)
                await self._update_metrics("failed", job)
                await self._publish_event("job_failed", job.to_dict())
            
            await self._save_job(job)
            
        finally:
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
            self._job_history.append(job)
    
    async def _dispatch_celery_task(self, job: ResearchJob) -> dict:
        """Dispatch job to Celery for background execution."""
        # Import here to avoid circular imports
        from app.services.research_pipeline.research_scheduler import run_research_analysis
        
        # Send task to Celery
        celery_task = run_research_analysis.delay(
            job_id=job.job_id,
            ticker=job.ticker,
            trigger_type=job.trigger_type.value,
            payload=job.payload,
        )
        
        # Wait for result with timeout
        result = celery_task.get(timeout=self.JOB_TIMEOUT_SECONDS)
        return result
    
    async def _save_job(self, job: ResearchJob) -> None:
        """Save job state to Redis."""
        await self.redis.setex(
            self.JOB_DATA_PREFIX.format(job_id=job.job_id),
            86400 * 7,  # 7 day TTL
            json.dumps(job.to_dict())
        )
    
    async def _restore_pending_jobs(self) -> None:
        """Restore pending jobs from previous session."""
        # This would scan for jobs that were running when shutdown occurred
        # and re-queue them
        pass
    
    async def _metrics_collection_loop(self) -> None:
        """Background task for collecting pipeline metrics."""
        while self._running:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=60  # Collect metrics every minute
                )
            except asyncio.TimeoutError:
                await self._collect_metrics()
    
    async def _collect_metrics(self) -> None:
        """Collect and store pipeline metrics."""
        stats = await self.get_queue_stats()
        
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queue_stats": stats,
            "active_jobs_count": len(self._active_jobs),
            "job_history_count": len(self._job_history),
        }
        
        await self.redis.setex(
            self.PIPELINE_METRICS_KEY,
            3600 * self.METRICS_RETENTION_HOURS,
            json.dumps(metrics)
        )
    
    async def _update_metrics(self, event_type: str, job: ResearchJob) -> None:
        """Update metrics based on job events."""
        metrics_key = f"research:metrics:{event_type}"
        await self.redis.incr(metrics_key)
        await self.redis.expire(metrics_key, 86400)
        
        # Track by trigger type
        trigger_key = f"research:metrics:trigger:{job.trigger_type.value}"
        await self.redis.incr(trigger_key)
        await self.redis.expire(trigger_key, 86400)
    
    def _get_default_metrics(self) -> dict:
        """Get default metrics structure."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queue_stats": {
                "queue_length": 0,
                "active_jobs": 0,
                "priority_distribution": {},
            },
            "active_jobs_count": 0,
            "job_history_count": 0,
        }
    
    async def _publish_event(self, event_type: str, data: dict) -> None:
        """Publish event to subscribers and Redis."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        
        # Publish to Redis
        await self.redis.publish("research:pipeline:events", json.dumps(event))
        
        # Notify local subscribers
        for callback in self._subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    async def _update_pipeline_state(self, state: str) -> None:
        """Update pipeline state in Redis."""
        await self.redis.hset(
            self.PIPELINE_STATE_KEY,
            mapping={
                "state": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )


# Global orchestrator instance
_orchestrator: Optional[PipelineOrchestrator] = None


async def get_orchestrator() -> PipelineOrchestrator:
    """Get or create the global pipeline orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PipelineOrchestrator()
        await _orchestrator.initialize()
    return _orchestrator


async def shutdown_orchestrator() -> None:
    """Shutdown the global orchestrator."""
    global _orchestrator
    if _orchestrator:
        await _orchestrator.shutdown()
        _orchestrator = None
