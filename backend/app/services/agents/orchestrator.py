"""
Agent Orchestrator for TradingBrowser.

Central service for managing agent lifecycle, task queues, shared memory,
and health tracking across the distributed agent system.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Coroutine, Optional, Type, TypeVar

import redis.asyncio as redis
from app.core.config import settings

from .base import AgentStatus, AgentTask, AgentOutput, BaseAgent

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseAgent)


class AgentOrchestrator:
    """
    Central orchestrator for the TradingBrowser agent system.
    
    Responsibilities:
    1. Manage agent lifecycle (pending, running, completed, error, idle)
    2. Handle task queue using Redis
    3. Coordinate agent communication via shared memory
    4. Track agent health with heartbeats and timeouts
    5. Provide monitoring and subscription interfaces
    """

    # Redis key prefixes
    TASK_QUEUE_KEY = "orchestrator:task_queue"
    AGENTS_KEY = "agents:registered"
    HEARTBEAT_PREFIX = "agent:{agent_id}:heartbeat"
    TASK_PREFIX = "task:{task_id}"
    OUTPUT_PREFIX = "output:{task_id}"
    SHARED_PREFIX = "shared:{key}"
    
    # Default timeouts
    DEFAULT_HEARTBEAT_TIMEOUT_SEC = 30.0
    DEFAULT_TASK_TIMEOUT_SEC = 300.0

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._agents: dict[str, BaseAgent] = {}  # Local agent instances
        self._running = False
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._subscribers: list[Callable[[dict], Coroutine]] = []
        self._shutdown_event = asyncio.Event()

    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def initialize(self) -> None:
        """Initialize the orchestrator and start background tasks."""
        # Test Redis connection
        await self.redis.ping()
        
        self._running = True
        self._queue_processor_task = asyncio.create_task(self._process_task_queue())
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Setup pubsub for output streaming
        self._pubsub = self.redis.pubsub()
        await self._pubsub.subscribe("agent:outputs:all")
        
        logger.info("AgentOrchestrator initialized")

    async def shutdown(self) -> None:
        """Gracefully shutdown the orchestrator."""
        self._running = False
        self._shutdown_event.set()
        
        # Shutdown all local agents
        for agent in self._agents.values():
            await agent.shutdown()
        
        # Cancel background tasks
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        
        if self._redis:
            await self._redis.close()
        
        logger.info("AgentOrchestrator shutdown complete")

    # =========================================================================
    # Agent Lifecycle Management
    # =========================================================================

    async def register_agent(self, agent: BaseAgent) -> None:
        """Register a local agent instance with the orchestrator."""
        await agent.initialize()
        self._agents[agent.agent_id] = agent
        logger.info(f"Registered agent {agent.agent_id} of type {agent.agent_type}")

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister and shutdown an agent."""
        if agent_id in self._agents:
            await self._agents[agent_id].shutdown()
            del self._agents[agent_id]
            logger.info(f"Unregistered agent {agent_id}")

    async def create_agent(
        self,
        agent_class: Type[T],
        agent_id: Optional[str] = None,
        **kwargs
    ) -> T:
        """Create and register a new agent instance."""
        agent = agent_class(
            agent_id=agent_id,
            redis_client=self.redis,
            **kwargs
        )
        await self.register_agent(agent)
        return agent

    # =========================================================================
    # Task Queue Management
    # =========================================================================

    async def submit_task(
        self,
        agent_type: str,
        payload: dict,
        priority: int = 5,
        parent_task_id: Optional[str] = None,
    ) -> str:
        """
        Submit a task to the queue.
        
        Args:
            agent_type: Type of agent to handle the task
            payload: Task-specific data
            priority: Task priority (1-10, lower is higher priority)
            parent_task_id: Optional parent task for task chaining
            
        Returns:
            task_id: Unique identifier for the task
        """
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        task = AgentTask(
            task_id=task_id,
            agent_type=agent_type,
            payload=payload,
            priority=priority,
            parent_task_id=parent_task_id,
        )
        
        # Store task and add to priority queue
        # Using Redis sorted set for priority queue (score = priority)
        await self.redis.setex(
            self.TASK_PREFIX.format(task_id=task_id),
            86400,  # 24 hour TTL
            json.dumps(task.to_dict())
        )
        await self.redis.zadd(
            self.TASK_QUEUE_KEY,
            {task_id: priority}
        )
        
        logger.info(f"Submitted task {task_id} for agent type {agent_type}")
        return task_id

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        # Remove from queue
        removed = await self.redis.zrem(self.TASK_QUEUE_KEY, task_id)
        
        if removed:
            # Update task status
            task_data = await self.redis.get(self.TASK_PREFIX.format(task_id=task_id))
            if task_data:
                task = AgentTask.from_dict(json.loads(task_data))
                task.status = AgentStatus.ERROR
                task.error_message = "Task cancelled by user"
                task.completed_at = datetime.now(timezone.utc)
                await self.redis.setex(
                    self.TASK_PREFIX.format(task_id=task_id),
                    86400,
                    json.dumps(task.to_dict())
                )
            logger.info(f"Cancelled task {task_id}")
            return True
        
        return False

    async def _process_task_queue(self) -> None:
        """Background task to process the task queue."""
        while not self._shutdown_event.is_set():
            try:
                # Get highest priority task (lowest score)
                task_ids = await self.redis.zrange(
                    self.TASK_QUEUE_KEY,
                    0,
                    0,
                    withscores=False
                )
                
                if not task_ids:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=0.5
                    )
                    continue
                
                task_id = task_ids[0]
                
                # Try to acquire task (remove from queue)
                acquired = await self.redis.zrem(self.TASK_QUEUE_KEY, task_id)
                
                if acquired:
                    await self._execute_task(task_id)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing task queue: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task_id: str) -> None:
        """Execute a task by finding or creating an appropriate agent."""
        task_data = await self.redis.get(self.TASK_PREFIX.format(task_id=task_id))
        if not task_data:
            logger.warning(f"Task {task_id} not found in storage")
            return
        
        task = AgentTask.from_dict(json.loads(task_data))
        
        try:
            # Find an idle agent of the right type
            agent = await self._find_idle_agent(task.agent_type)
            
            if agent is None:
                # No idle agent available, requeue with slight delay
                await self.redis.zadd(
                    self.TASK_QUEUE_KEY,
                    {task_id: task.priority}
                )
                logger.debug(f"Requeued task {task_id} - no idle agents available")
                return
            
            # Execute the task
            output = await agent.execute(task)
            logger.info(f"Task {task_id} completed with status {output.status.value}")
            
        except Exception as e:
            logger.exception(f"Error executing task {task_id}")
            # Mark task as failed
            task.status = AgentStatus.ERROR
            task.error_message = str(e)
            task.completed_at = datetime.now(timezone.utc)
            await self.redis.setex(
                self.TASK_PREFIX.format(task_id=task_id),
                86400,
                json.dumps(task.to_dict())
            )

    async def _find_idle_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Find an idle agent of the specified type."""
        for agent in self._agents.values():
            if agent.agent_type == agent_type and agent.status == AgentStatus.IDLE:
                return agent
        return None

    # =========================================================================
    # Health Tracking
    # =========================================================================

    async def _health_check_loop(self) -> None:
        """Background task to monitor agent health."""
        while not self._shutdown_event.is_set():
            try:
                await self._check_agent_health()
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.DEFAULT_HEARTBEAT_TIMEOUT_SEC
                )
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(1)

    async def _check_agent_health(self) -> None:
        """Check health of all registered agents."""
        agent_ids = await self.redis.smembers(self.AGENTS_KEY)
        
        for agent_id in agent_ids:
            try:
                heartbeat_key = self.HEARTBEAT_PREFIX.format(agent_id=agent_id)
                heartbeat_data = await self.redis.hgetall(heartbeat_key)
                
                if not heartbeat_data:
                    # No heartbeat found - agent may be dead
                    logger.warning(f"Agent {agent_id} has no heartbeat")
                    await self._mark_agent_timeout(agent_id)
                    continue
                
                # Check heartbeat timestamp
                last_timestamp = heartbeat_data.get("timestamp")
                if last_timestamp:
                    last_heartbeat = datetime.fromisoformat(last_timestamp)
                    elapsed = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()
                    
                    if elapsed > self.DEFAULT_HEARTBEAT_TIMEOUT_SEC:
                        logger.warning(f"Agent {agent_id} heartbeat timeout ({elapsed:.1f}s)")
                        await self._mark_agent_timeout(agent_id)
                
            except Exception as e:
                logger.error(f"Error checking health for agent {agent_id}: {e}")

    async def _mark_agent_timeout(self, agent_id: str) -> None:
        """Mark an agent as timed out."""
        await self.redis.hset(
            f"agent:{agent_id}",
            "status",
            AgentStatus.TIMEOUT.value
        )
        
        # If it's a local agent, remove it
        if agent_id in self._agents:
            await self.unregister_agent(agent_id)

    # =========================================================================
    # Public API Methods
    # =========================================================================

    async def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        agent_type: Optional[str] = None,
    ) -> list[dict]:
        """
        List all registered agents with optional filtering.
        
        Args:
            status: Filter by agent status
            agent_type: Filter by agent type
            
        Returns:
            List of agent information dictionaries
        """
        agent_ids = await self.redis.smembers(self.AGENTS_KEY)
        agents = []
        
        for agent_id in agent_ids:
            try:
                agent_data = await self.redis.hgetall(f"agent:{agent_id}")
                if not agent_data:
                    continue
                
                # Parse stored data
                info = {}
                for k, v in agent_data.items():
                    try:
                        info[k] = json.loads(v)
                    except json.JSONDecodeError:
                        info[k] = v
                
                # Apply filters
                if status and info.get("status") != status.value:
                    continue
                if agent_type and info.get("agent_type") != agent_type:
                    continue
                
                # Add heartbeat info
                heartbeat = await self.redis.hgetall(
                    self.HEARTBEAT_PREFIX.format(agent_id=agent_id)
                )
                if heartbeat:
                    info["heartbeat"] = {
                        k: json.loads(v) if v.startswith("{") else v
                        for k, v in heartbeat.items()
                    }
                
                agents.append(info)
                
            except Exception as e:
                logger.error(f"Error fetching agent {agent_id}: {e}")
        
        return agents

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        """
        Get detailed information about a specific agent.
        
        Args:
            agent_id: The agent's unique identifier
            
        Returns:
            Agent information dictionary or None if not found
        """
        agent_data = await self.redis.hgetall(f"agent:{agent_id}")
        if not agent_data:
            return None
        
        info = {}
        for k, v in agent_data.items():
            try:
                info[k] = json.loads(v)
            except json.JSONDecodeError:
                info[k] = v
        
        # Add heartbeat
        heartbeat = await self.redis.hgetall(
            self.HEARTBEAT_PREFIX.format(agent_id=agent_id)
        )
        if heartbeat:
            info["heartbeat"] = {
                k: json.loads(v) if v.startswith("{") else v
                for k, v in heartbeat.items()
            }
        
        # Add current task if any
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            if agent.current_task:
                info["current_task"] = agent.current_task.to_dict()
        
        # Add task history
        task_ids = await self.redis.smembers(f"agent:{agent_id}:tasks")
        info["task_count"] = len(task_ids)
        
        return info

    async def get_logs(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get logs for an agent or task.
        
        Args:
            agent_id: Filter by agent ID
            task_id: Filter by task ID
            limit: Maximum number of log entries
            
        Returns:
            List of log entries
        """
        logs = []
        
        if task_id:
            # Get logs from task output
            output_data = await self.redis.get(self.OUTPUT_PREFIX.format(task_id=task_id))
            if output_data:
                output = AgentOutput.from_dict(json.loads(output_data))
                logs = output.logs
        
        elif agent_id:
            # Get logs from all outputs for this agent
            output_ids = await self.redis.smembers(f"agent:{agent_id}:outputs")
            for output_id in list(output_ids)[:limit]:
                output_data = await self.redis.get(self.OUTPUT_PREFIX.format(task_id=output_id))
                if output_data:
                    output = AgentOutput.from_dict(json.loads(output_data))
                    for log in output.logs:
                        log["task_id"] = output.task_id
                        logs.append(log)
            
            # Sort by timestamp
            logs.sort(key=lambda x: x.get("timestamp", ""))
            logs = logs[-limit:]
        
        return logs

    async def get_outputs(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        status: Optional[AgentStatus] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get agent outputs with optional filtering.
        
        Args:
            agent_id: Filter by agent ID
            task_id: Filter by task ID (returns single item if found)
            status: Filter by output status
            limit: Maximum number of outputs
            
        Returns:
            List of output dictionaries
        """
        outputs = []
        
        if task_id:
            # Get specific output
            output_data = await self.redis.get(self.OUTPUT_PREFIX.format(task_id=task_id))
            if output_data:
                output = AgentOutput.from_dict(json.loads(output_data))
                if not status or output.status == status:
                    outputs = [output.to_dict()]
        
        elif agent_id:
            # Get all outputs for agent
            output_ids = await self.redis.smembers(f"agent:{agent_id}:outputs")
            for output_id in list(output_ids)[:limit]:
                output_data = await self.redis.get(self.OUTPUT_PREFIX.format(task_id=output_id))
                if output_data:
                    output = AgentOutput.from_dict(json.loads(output_data))
                    if not status or output.status == status:
                        outputs.append(output.to_dict())
        
        else:
            # Get all recent outputs (scan Redis)
            cursor = 0
            count = 0
            while count < limit:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match="output:*",
                    count=100
                )
                for key in keys:
                    output_data = await self.redis.get(key)
                    if output_data:
                        output = AgentOutput.from_dict(json.loads(output_data))
                        if not status or output.status == status:
                            outputs.append(output.to_dict())
                            count += 1
                            if count >= limit:
                                break
                if cursor == 0:
                    break
        
        return outputs

    async def subscribe_to_updates(
        self,
        callback: Callable[[dict], Coroutine],
        agent_id: Optional[str] = None,
    ) -> None:
        """
        Subscribe to agent output updates.
        
        Args:
            callback: Async function to call with update data
            agent_id: Optional agent ID to filter updates (None = all agents)
        """
        self._subscribers.append((agent_id, callback))
        
        # Start listener if not already running
        if not hasattr(self, '_subscriber_task') or self._subscriber_task.done():
            self._subscriber_task = asyncio.create_task(self._subscriber_loop())

    async def _subscriber_loop(self) -> None:
        """Listen for Redis pub/sub messages and dispatch to subscribers."""
        if not self._pubsub:
            return
        
        async for message in self._pubsub.listen():
            if message["type"] != "message":
                continue
            
            try:
                data = json.loads(message["data"])
                
                # Dispatch to matching subscribers
                for agent_id_filter, callback in self._subscribers:
                    if agent_id_filter is None or data.get("agent_id") == agent_id_filter:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback: {e}")
            
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in pubsub message: {message['data']}")

    async def unsubscribe(self, callback: Callable[[dict], Coroutine]) -> None:
        """Unsubscribe a callback from updates."""
        self._subscribers = [
            (agent_id, cb) for agent_id, cb in self._subscribers
            if cb != callback
        ]

    # =========================================================================
    # Shared Memory Operations
    # =========================================================================

    async def get_shared(self, key: str) -> Optional[any]:
        """Get a value from shared memory."""
        value = await self.redis.get(self.SHARED_PREFIX.format(key=key))
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set_shared(
        self,
        key: str,
        value: any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a value in shared memory."""
        serialized = json.dumps(value) if not isinstance(value, str) else value
        key = self.SHARED_PREFIX.format(key=key)
        if ttl:
            await self.redis.setex(key, ttl, serialized)
        else:
            await self.redis.set(key, serialized)

    async def delete_shared(self, key: str) -> None:
        """Delete a value from shared memory."""
        await self.redis.delete(self.SHARED_PREFIX.format(key=key))

    async def publish_channel(self, channel: str, message: dict) -> None:
        """Publish a message to a channel for inter-agent communication."""
        await self.redis.publish(
            f"channel:{channel}",
            json.dumps(message)
        )

    # =========================================================================
    # Task Status Helpers
    # =========================================================================

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get task by ID."""
        task_data = await self.redis.get(self.TASK_PREFIX.format(task_id=task_id))
        if task_data:
            return AgentTask.from_dict(json.loads(task_data))
        return None

    async def get_task_status(self, task_id: str) -> Optional[AgentStatus]:
        """Get the status of a task."""
        task = await self.get_task(task_id)
        return task.status if task else None


# Singleton instance
_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


async def initialize_orchestrator() -> AgentOrchestrator:
    """Initialize the orchestrator singleton."""
    orchestrator = get_orchestrator()
    await orchestrator.initialize()
    return orchestrator


async def shutdown_orchestrator() -> None:
    """Shutdown the orchestrator singleton."""
    global _orchestrator
    if _orchestrator:
        await _orchestrator.shutdown()
        _orchestrator = None