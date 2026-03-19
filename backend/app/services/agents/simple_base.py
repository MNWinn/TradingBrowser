"""
Simple Agent Base - No Redis Required

Provides the foundation for agents without Redis dependency.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


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
    priority: int = 5
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.PENDING
    error_message: Optional[str] = None
    parent_task_id: Optional[str] = None


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


class SimpleBaseAgent(ABC):
    """
    Simple base class for agents without Redis dependency.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        heartbeat_interval_sec: float = 5.0,
        timeout_sec: float = 300.0,
    ):
        self.agent_id = agent_id or f"{self.__class__.__name__.lower()}-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type or self.__class__.__name__
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.timeout_sec = timeout_sec
        
        self.status = AgentStatus.IDLE
        self.current_task: Optional[AgentTask] = None
        self._logs: list = []
        self._start_time: Optional[float] = None

    async def initialize(self) -> None:
        """Initialize the agent."""
        self.status = AgentStatus.IDLE

    async def shutdown(self) -> None:
        """Gracefully shutdown the agent."""
        self.status = AgentStatus.IDLE

    async def execute(self, task: AgentTask) -> AgentOutput:
        """Execute a task."""
        self.current_task = task
        self.status = AgentStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        self._start_time = time.perf_counter()
        
        try:
            result = await self._run(task.payload)
            task.status = AgentStatus.COMPLETED
            status = AgentStatus.COMPLETED
        except Exception as e:
            result = {"error": str(e)}
            task.status = AgentStatus.ERROR
            status = AgentStatus.ERROR
            task.error_message = str(e)
        
        task.completed_at = datetime.now(timezone.utc)
        self.status = AgentStatus.IDLE
        
        execution_time_ms = (time.perf_counter() - self._start_time) * 1000 if self._start_time else None
        
        return AgentOutput(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=status,
            result=result,
            logs=self._logs.copy(),
            execution_time_ms=execution_time_ms,
        )

    @abstractmethod
    async def _run(self, payload: dict) -> dict:
        """Override this method with agent logic."""
        pass

    def log(self, message: str, level: str = "info") -> None:
        """Log a message."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        self._logs.append(entry)
