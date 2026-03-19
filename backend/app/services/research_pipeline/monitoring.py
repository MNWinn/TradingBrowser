"""
Pipeline Monitoring and Metrics for TradingBrowser.

Provides comprehensive logging, metrics collection, and health monitoring
for the research pipeline.
"""

import json
import logging
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """Represents a metric data point."""
    name: str
    metric_type: MetricType
    value: float
    labels: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PipelineHealth:
    """Pipeline health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    components: dict
    last_check: datetime
    issues: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "components": self.components,
            "last_check": self.last_check.isoformat(),
            "issues": self.issues,
        }


class PipelineMonitor:
    """
    Comprehensive monitoring for the research pipeline.
    
    Features:
    - Metrics collection and storage
    - Health checks
    - Performance monitoring
    - Alert generation
    """
    
    # Redis key prefixes
    METRICS_KEY_PREFIX = "monitor:metric:{name}"
    HEALTH_KEY = "monitor:health"
    ALERTS_KEY = "monitor:alerts"
    PERFORMANCE_KEY = "monitor:performance"
    
    # Configuration
    METRICS_RETENTION_HOURS = 24
    HEALTH_CHECK_INTERVAL = 60  # seconds
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._metrics_buffer: deque = deque(maxlen=1000)
        self._performance_data: dict[str, list] = defaultdict(list)
        
    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[dict] = None,
    ) -> None:
        """
        Record a metric.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            labels: Optional labels for the metric
        """
        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            labels=labels or {},
        )
        
        # Buffer for batch processing
        self._metrics_buffer.append(metric)
        
        # Store in Redis
        key = self.METRICS_KEY_PREFIX.format(name=name)
        await self.redis.lpush(key, json.dumps(metric.to_dict()))
        await self.redis.ltrim(key, 0, 999)  # Keep last 1000
        await self.redis.expire(key, 3600 * self.METRICS_RETENTION_HOURS)
        
        logger.debug(f"Metric recorded: {name} = {value}")
    
    async def increment_counter(
        self,
        name: str,
        value: float = 1,
        labels: Optional[dict] = None,
    ) -> None:
        """Increment a counter metric."""
        await self.record_metric(name, value, MetricType.COUNTER, labels)
        
        # Also increment in Redis for quick access
        counter_key = f"monitor:counter:{name}"
        await self.redis.incrbyfloat(counter_key, value)
        await self.redis.expire(counter_key, 86400)
    
    async def record_timing(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[dict] = None,
    ) -> None:
        """Record a timing metric."""
        await self.record_metric(name, duration_ms, MetricType.TIMER, labels)
        
        # Track in performance data
        self._performance_data[name].append({
            "value": duration_ms,
            "timestamp": time.time(),
        })
        
        # Clean old entries
        cutoff = time.time() - 3600  # 1 hour
        self._performance_data[name] = [
            e for e in self._performance_data[name] if e["timestamp"] > cutoff
        ]
    
    @contextmanager
    def timer(self, name: str, labels: Optional[dict] = None):
        """Context manager for timing operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Use asyncio.create_task for async context
            import asyncio
            asyncio.create_task(self.record_timing(name, duration_ms, labels))
    
    async def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[MetricType] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get recorded metrics."""
        if name:
            key = self.METRICS_KEY_PREFIX.format(name=name)
            metrics_json = await self.redis.lrange(key, 0, limit - 1)
            return [json.loads(m) for m in metrics_json]
        
        # Get all metrics
        all_metrics = []
        pattern = self.METRICS_KEY_PREFIX.format(name="*")
        keys = await self.redis.keys(pattern)
        
        for key in keys[:10]:  # Limit to 10 metric types
            metrics_json = await self.redis.lrange(key, 0, limit - 1)
            for m in metrics_json:
                metric = json.loads(m)
                if metric_type is None or metric.get("type") == metric_type.value:
                    all_metrics.append(metric)
        
        return sorted(all_metrics, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    async def get_counter(self, name: str) -> float:
        """Get current counter value."""
        counter_key = f"monitor:counter:{name}"
        value = await self.redis.get(counter_key)
        return float(value) if value else 0.0
    
    async def get_performance_stats(self, name: str) -> dict:
        """Get performance statistics for a metric."""
        data = self._performance_data.get(name, [])
        
        if not data:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0}
        
        values = [d["value"] for d in data]
        values.sort()
        
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": values[0],
            "max": values[-1],
            "p95": values[int(len(values) * 0.95)] if len(values) > 1 else values[0],
        }
    
    async def check_health(self) -> PipelineHealth:
        """Check pipeline health status."""
        components = {}
        issues = []
        
        # Check Redis connection
        try:
            await self.redis.ping()
            components["redis"] = {"status": "healthy", "latency_ms": 0}
        except Exception as e:
            components["redis"] = {"status": "unhealthy", "error": str(e)}
            issues.append(f"Redis connection failed: {e}")
        
        # Check queue depths
        try:
            pipeline_queue = await self.redis.zcard("research:job_queue")
            signal_queue = await self.redis.zcard("router:signal_queue")
            
            components["queues"] = {
                "pipeline_queue": pipeline_queue,
                "signal_queue": signal_queue,
            }
            
            if pipeline_queue > 1000:
                issues.append(f"Pipeline queue backlog: {pipeline_queue} jobs")
            if signal_queue > 1000:
                issues.append(f"Signal queue backlog: {signal_queue} signals")
                
        except Exception as e:
            components["queues"] = {"status": "error", "error": str(e)}
        
        # Check Celery workers
        try:
            from app.workers.celery_app import celery_app
            inspect = celery_app.control.inspect()
            active = inspect.active()
            
            components["celery"] = {
                "status": "healthy" if active else "no_workers",
                "active_workers": len(active) if active else 0,
            }
            
            if not active:
                issues.append("No Celery workers detected")
                
        except Exception as e:
            components["celery"] = {"status": "error", "error": str(e)}
        
        # Determine overall status
        if any(c.get("status") == "unhealthy" for c in components.values()):
            status = "unhealthy"
        elif issues:
            status = "degraded"
        else:
            status = "healthy"
        
        health = PipelineHealth(
            status=status,
            components=components,
            last_check=datetime.now(timezone.utc),
            issues=issues,
        )
        
        # Store health status
        await self.redis.setex(
            self.HEALTH_KEY,
            300,  # 5 minute TTL
            json.dumps(health.to_dict())
        )
        
        return health
    
    async def get_health_status(self) -> Optional[dict]:
        """Get cached health status."""
        data = await self.redis.get(self.HEALTH_KEY)
        if data:
            return json.loads(data)
        return None
    
    async def generate_alert(self, level: str, message: str, data: Optional[dict] = None) -> dict:
        """Generate a monitoring alert."""
        alert = {
            "id": f"alert-{int(time.time() * 1000)}",
            "level": level,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        }
        
        await self.redis.lpush(self.ALERTS_KEY, json.dumps(alert))
        await self.redis.ltrim(self.ALERTS_KEY, 0, 999)
        
        logger.warning(f"Monitor alert [{level}]: {message}")
        
        return alert
    
    async def get_alerts(
        self,
        level: Optional[str] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get monitoring alerts."""
        alerts_json = await self.redis.lrange(self.ALERTS_KEY, 0, limit - 1)
        alerts = [json.loads(a) for a in alerts_json]
        
        if level:
            alerts = [a for a in alerts if a.get("level") == level]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.get("acknowledged") == acknowledged]
        
        return alerts
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        alerts_json = await self.redis.lrange(self.ALERTS_KEY, 0, -1)
        
        for i, alert_json in enumerate(alerts_json):
            alert = json.loads(alert_json)
            if alert.get("id") == alert_id:
                alert["acknowledged"] = True
                await self.redis.lset(self.ALERTS_KEY, i, json.dumps(alert))
                return True
        
        return False
    
    async def get_dashboard_data(self) -> dict:
        """Get data for monitoring dashboard."""
        health = await self.get_health_status() or (await self.check_health()).to_dict()
        
        # Get key metrics
        jobs_submitted = await self.get_counter("jobs_submitted")
        jobs_completed = await self.get_counter("jobs_completed")
        jobs_failed = await self.get_counter("jobs_failed")
        signals_routed = await self.get_counter("signals_routed")
        
        # Get performance stats
        job_duration = await self.get_performance_stats("job_execution_time")
        
        # Get recent alerts
        alerts = await self.get_alerts(limit=10)
        
        return {
            "health": health,
            "metrics": {
                "jobs_submitted": jobs_submitted,
                "jobs_completed": jobs_completed,
                "jobs_failed": jobs_failed,
                "signals_routed": signals_routed,
                "success_rate": (jobs_completed / max(jobs_submitted, 1)) * 100,
            },
            "performance": {
                "job_execution_time": job_duration,
            },
            "recent_alerts": alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global monitor instance
_monitor: Optional[PipelineMonitor] = None


async def get_monitor() -> PipelineMonitor:
    """Get or create the global monitor."""
    global _monitor
    if _monitor is None:
        _monitor = PipelineMonitor()
    return _monitor


def monitored(metric_name: str, metric_type: MetricType = MetricType.TIMER):
    """Decorator for monitoring function execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = await get_monitor()
            start = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                await monitor.increment_counter(f"{metric_name}_success")
                return result
            except Exception as e:
                await monitor.increment_counter(f"{metric_name}_errors")
                raise
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                await monitor.record_timing(metric_name, duration_ms)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                # Can't await in sync context, just log
                logger.debug(f"{metric_name} took {duration_ms:.2f}ms")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
