"""
Base Agent class for TradingBrowser agent system.

Provides the foundation for all agents with lifecycle management,
heartbeat mechanisms, and shared memory coordination.
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Callable, Coroutine, Optional

import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    IDLE = "idle"
    TIMEOUT = "timeout"


@dataclass
class AgentTask:
    """Task definition for agent execution."""
    task_id: str
    agent_type: str
    payload: dict
    priority: int = 5  # 1-10, lower is higher priority
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.PENDING
    error_message: Optional[str] = None
    parent_task_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "payload": self.payload,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "error_message": self.error_message,
            "parent_task_id": self.parent_task_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTask":
        return cls(
            task_id=data["task_id"],
            agent_type=data["agent_type"],
            payload=data["payload"],
            priority=data.get("priority", 5),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            status=AgentStatus(data.get("status", "pending")),
            error_message=data.get("error_message"),
            parent_task_id=data.get("parent_task_id"),
        )


@dataclass
class AgentOutput:
    """Output from agent execution."""
    task_id: str
    agent_id: str
    status: AgentStatus
    result: Optional[dict] = None
    logs: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "result": self.result,
            "logs": self.logs,
            "metrics": self.metrics,
            "created_at": self.created_at.isoformat(),
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentOutput":
        return cls(
            task_id=data["task_id"],
            agent_id=data["agent_id"],
            status=AgentStatus(data.get("status", "pending")),
            result=data.get("result"),
            logs=data.get("logs", []),
            metrics=data.get("metrics", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            execution_time_ms=data.get("execution_time_ms"),
        )


class BaseAgent(ABC):
    """
    Base class for all TradingBrowser agents.
    
    Provides:
    - Lifecycle management (pending -> running -> completed/error/idle)
    - Heartbeat mechanism for health tracking
    - Shared memory access via Redis
    - Structured logging and output capture
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        self.agent_id = agent_id or f"{self.__class__.__name__.lower()}-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type or self.__class__.__name__
        self.redis = redis_client
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.timeout_sec = timeout_sec
        
        self.status = AgentStatus.IDLE
        self.current_task: Optional[AgentTask] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._logs: list = []
        self._outputs: list = []
        self._start_time: Optional[float] = None
        self._shutdown_event = asyncio.Event()

    @property
    def redis_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self.redis is None:
            self.redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self.redis

    async def initialize(self) -> None:
        """Initialize the agent and register with orchestrator."""
        await self._register_agent()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Agent {self.agent_id} initialized")

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent."""
        self._shutdown_event.set()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        await self._update_agent_state(AgentStatus.IDLE)
        logger.info(f"Agent {self.agent_id} shutdown complete")

    async def _register_agent(self) -> None:
        """Register agent in shared memory."""
        agent_data = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "heartbeat_interval_sec": self.heartbeat_interval_sec,
            "timeout_sec": self.timeout_sec,
        }
        await self.redis_client.hset(
            f"agent:{self.agent_id}",
            mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in agent_data.items()}
        )
        await self.redis_client.sadd("agents:registered", self.agent_id)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to indicate agent health."""
        while not self._shutdown_event.is_set():
            try:
                await self._send_heartbeat()
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.heartbeat_interval_sec
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Heartbeat error for {self.agent_id}: {e}")
                await asyncio.sleep(1)

    async def _send_heartbeat(self) -> None:
        """Send heartbeat to Redis."""
        heartbeat_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": self.status.value,
            "task_id": self.current_task.task_id if self.current_task else None,
        }
        await self.redis_client.hset(
            f"agent:{self.agent_id}:heartbeat",
            mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in heartbeat_data.items()}
        )
        await self.redis_client.expire(f"agent:{self.agent_id}:heartbeat", int(self.timeout_sec * 2))

    async def _update_agent_state(self, status: AgentStatus) -> None:
        """Update agent status in shared memory."""
        self.status = status
        await self.redis_client.hset(
            f"agent:{self.agent_id}",
            "status",
            status.value
        )
        await self.redis_client.hset(
            f"agent:{self.agent_id}",
            "last_updated",
            datetime.now(timezone.utc).isoformat()
        )

    async def execute(self, task: AgentTask) -> AgentOutput:
        """
        Execute a task with full lifecycle management.
        
        Handles:
        - Status transitions
        - Logging capture
        - Error handling
        - Output storage
        """
        self.current_task = task
        self._logs = []
        self._outputs = []
        self._start_time = time.perf_counter()
        
        await self._update_agent_state(AgentStatus.RUNNING)
        task.started_at = datetime.now(timezone.utc)
        
        try:
            # Store task in shared memory
            await self._store_task(task)
            
            # Execute the agent-specific logic
            result = await self._run(task.payload)
            
            execution_time_ms = (time.perf_counter() - self._start_time) * 1000
            
            output = AgentOutput(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.COMPLETED,
                result=result,
                logs=self._logs,
                metrics={"execution_time_ms": execution_time_ms},
                execution_time_ms=execution_time_ms,
            )
            
            task.status = AgentStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            await self._update_agent_state(AgentStatus.IDLE)
            
        except Exception as e:
            execution_time_ms = (time.perf_counter() - self._start_time) * 1000 if self._start_time else None
            
            logger.exception(f"Agent {self.agent_id} task {task.task_id} failed")
            
            output = AgentOutput(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                result={"error": str(e), "error_type": type(e).__name__},
                logs=self._logs + [f"ERROR: {str(e)}"],
                metrics={"execution_time_ms": execution_time_ms},
                execution_time_ms=execution_time_ms,
            )
            
            task.status = AgentStatus.ERROR
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            await self._update_agent_state(AgentStatus.ERROR)
        
        finally:
            # Store output in shared memory
            await self._store_output(output)
            await self._store_task(task)
            self.current_task = None
        
        return output

    @abstractmethod
    async def _run(self, payload: dict) -> dict:
        """
        Implement agent-specific logic here.
        
        Args:
            payload: Task-specific data
            
        Returns:
            Dict containing the agent's output
        """
        pass

    def log(self, message: str, level: str = "info") -> None:
        """Add a log entry."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {"timestamp": timestamp, "level": level, "message": message}
        self._logs.append(entry)
        
        # Also log to standard logger
        getattr(logger, level, logger.info)(f"[{self.agent_id}] {message}")

    async def _store_task(self, task: AgentTask) -> None:
        """Store task state in shared memory."""
        await self.redis_client.setex(
            f"task:{task.task_id}",
            86400,  # 24 hour TTL
            json.dumps(task.to_dict())
        )
        await self.redis_client.sadd(f"agent:{self.agent_id}:tasks", task.task_id)

    async def _store_output(self, output: AgentOutput) -> None:
        """Store output in shared memory."""
        await self.redis_client.setex(
            f"output:{output.task_id}",
            86400,  # 24 hour TTL
            json.dumps(output.to_dict())
        )
        await self.redis_client.sadd(f"agent:{self.agent_id}:outputs", output.task_id)
        
        # Publish output for subscribers
        await self.redis_client.publish(
            f"agent:{self.agent_id}:outputs",
            json.dumps(output.to_dict())
        )
        await self.redis_client.publish(
            "agent:outputs:all",
            json.dumps({"agent_id": self.agent_id, "output": output.to_dict()})
        )

    # Shared memory operations
    async def get_shared(self, key: str) -> Optional[Any]:
        """Get value from shared memory."""
        value = await self.redis_client.get(f"shared:{key}")
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set_shared(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in shared memory."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            await self.redis_client.setex(f"shared:{key}", ttl, serialized)
        else:
            await self.redis_client.set(f"shared:{key}", serialized)

    async def delete_shared(self, key: str) -> None:
        """Delete value from shared memory."""
        await self.redis_client.delete(f"shared:{key}")

    async def publish_message(self, channel: str, message: dict) -> None:
        """Publish message to a channel for inter-agent communication."""
        await self.redis_client.publish(
            f"channel:{channel}",
            json.dumps({"from": self.agent_id, "message": message})
        )

    async def get_agent_info(self) -> dict:
        """Get current agent information."""
        data = await self.redis_client.hgetall(f"agent:{self.agent_id}")
        heartbeat = await self.redis_client.hgetall(f"agent:{self.agent_id}:heartbeat")
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "registered_info": {k: json.loads(v) if v.startswith("{") else v for k, v in data.items()},
            "last_heartbeat": {k: json.loads(v) if v.startswith("{") else v for k, v in heartbeat.items()},
        }


class ExampleAgent(BaseAgent):
    """Example agent implementation for testing."""
    
    async def _run(self, payload: dict) -> dict:
        """Example implementation that just echoes the payload."""
        self.log(f"Processing payload: {payload}")
        await asyncio.sleep(0.1)  # Simulate work
        return {
            "echo": payload,
            "processed_by": self.agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }