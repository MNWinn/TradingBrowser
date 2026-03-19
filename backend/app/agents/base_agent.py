"""
Base Agent Class

All trading research agents inherit from this base class.
Provides common functionality for state management, messaging, and lifecycle.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import asyncio
import uuid

from .message_bus import MessageBus, AgentMessage, MessageType, get_message_bus


class AgentState(Enum):
    """Possible states for an agent."""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()
    SHUTDOWN = auto()


@dataclass
class AgentMetrics:
    """Metrics for agent performance tracking."""
    messages_processed: int = 0
    messages_sent: int = 0
    errors: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_active: Optional[datetime] = None
    total_processing_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0
    
    def record_processing_time(self, ms: float):
        """Record a processing time sample."""
        self.total_processing_time_ms += ms
        self.messages_processed += 1
        self.avg_processing_time_ms = (
            self.total_processing_time_ms / self.messages_processed
        )
        self.last_active = datetime.utcnow()
        
    def record_error(self):
        """Record an error."""
        self.errors += 1
        
    def record_task_completed(self):
        """Record a completed task."""
        self.tasks_completed += 1
        
    def record_task_failed(self):
        """Record a failed task."""
        self.tasks_failed += 1


class BaseAgent(ABC):
    """
    Base class for all trading research agents.
    
    Provides:
    - State management (IDLE, RUNNING, PAUSED, ERROR, SHUTDOWN)
    - Message bus integration
    - Metrics tracking
    - Lifecycle management (start, stop, pause, resume)
    - Task scheduling and execution
    """
    
    def __init__(
        self,
        agent_id: str,
        message_bus: Optional[MessageBus] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.agent_id = agent_id
        self.message_bus = message_bus or get_message_bus()
        self.config = config or {}
        
        # State
        self.state = AgentState.IDLE
        self.state_history: List[tuple] = []
        
        # Metrics
        self.metrics = AgentMetrics()
        
        # Task management
        self._tasks: set = set()
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Subscriptions
        self._subscriptions: List[tuple] = []
        
        # Message handlers
        self._message_handlers: Dict[MessageType, callable] = {}
        
    def _change_state(self, new_state: AgentState, reason: str = ""):
        """Change agent state and record history."""
        old_state = self.state
        self.state = new_state
        self.state_history.append((
            datetime.utcnow(),
            old_state.name if old_state else None,
            new_state.name,
            reason
        ))
        
        # Publish state change
        asyncio.create_task(self.send_message(
            MessageType.AGENT_STATUS,
            {
                "agent_id": self.agent_id,
                "state": new_state.name,
                "previous_state": old_state.name if old_state else None,
                "reason": reason,
            }
        ))
        
    async def start(self):
        """Start the agent."""
        if self.state == AgentState.RUNNING:
            return
            
        self._running = True
        self._change_state(AgentState.RUNNING, "Agent started")
        
        # Subscribe to message types
        for msg_type, handler in self._message_handlers.items():
            await self.message_bus.subscribe(msg_type, self._wrap_handler(handler))
            self._subscriptions.append((msg_type, handler))
            
        # Subscribe to direct messages
        await self.message_bus.subscribe_to_agent(
            self.agent_id, 
            self._handle_direct_message
        )
        
        # Run agent-specific startup
        await self.on_start()
        
    async def stop(self):
        """Stop the agent gracefully."""
        self._running = False
        self._change_state(AgentState.SHUTDOWN, "Agent stopping")
        self._shutdown_event.set()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        # Unsubscribe from messages
        for msg_type, handler in self._subscriptions:
            await self.message_bus.unsubscribe(msg_type, self._wrap_handler(handler))
            
        self._subscriptions = []
        
        # Run agent-specific shutdown
        await self.on_stop()
        
    async def pause(self):
        """Pause the agent temporarily."""
        if self.state == AgentState.RUNNING:
            self._change_state(AgentState.PAUSED, "Agent paused")
            await self.on_pause()
            
    async def resume(self):
        """Resume a paused agent."""
        if self.state == AgentState.PAUSED:
            self._change_state(AgentState.RUNNING, "Agent resumed")
            await self.on_resume()
            
    def _wrap_handler(self, handler):
        """Wrap a message handler with error handling and metrics."""
        async def wrapped(message: AgentMessage):
            if not self._running or self.state != AgentState.RUNNING:
                return
                
            start_time = datetime.utcnow()
            try:
                await handler(message)
                
                # Update metrics
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                self.metrics.record_processing_time(processing_time)
                
            except Exception as e:
                self.metrics.record_error()
                self._change_state(AgentState.ERROR, f"Handler error: {str(e)}")
                await self.handle_error(e, message)
                
        return wrapped
        
    async def _handle_direct_message(self, message: AgentMessage):
        """Handle messages targeted directly at this agent."""
        # Check for control messages
        if message.msg_type == MessageType.TASK_ASSIGNMENT:
            await self._handle_task_assignment(message)
        elif message.msg_type == MessageType.SHUTDOWN:
            await self.stop()
            
    async def _handle_task_assignment(self, message: AgentMessage):
        """Handle a task assignment from the supervisor."""
        task = message.payload.get("task")
        if task:
            asyncio.create_task(self.execute_task(task))
            
    async def send_message(
        self,
        msg_type: MessageType,
        payload: Dict[str, Any],
        target: Optional[str] = None,
        priority: int = 5
    ) -> bool:
        """Send a message to the bus."""
        message = AgentMessage(
            msg_type=msg_type,
            source=self.agent_id,
            target=target,
            payload=payload,
            priority=priority
        )
        
        success = await self.message_bus.publish(message)
        if success:
            self.metrics.messages_sent += 1
        return success
        
    async def request(
        self,
        target: str,
        msg_type: MessageType,
        payload: Dict[str, Any],
        timeout_sec: float = 30.0
    ) -> Optional[AgentMessage]:
        """Send a request to another agent and wait for response."""
        message = AgentMessage(
            msg_type=msg_type,
            source=self.agent_id,
            target=target,
            payload=payload
        )
        
        return await self.message_bus.request(message, timeout_sec)
        
    def register_handler(self, msg_type: MessageType, handler: callable):
        """Register a handler for a specific message type."""
        self._message_handlers[msg_type] = handler
        
    async def execute_task(self, task: Dict[str, Any]):
        """Execute a task assigned by the supervisor."""
        task_id = task.get("task_id", str(uuid.uuid4()))
        
        try:
            result = await self.process_task(task)
            self.metrics.record_task_completed()
            
            # Send completion message
            await self.send_message(
                MessageType.AGENT_STATUS,
                {
                    "agent_id": self.agent_id,
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                }
            )
            
        except Exception as e:
            self.metrics.record_task_failed()
            
            # Send failure message
            await self.send_message(
                MessageType.ERROR,
                {
                    "agent_id": self.agent_id,
                    "task_id": task_id,
                    "error": str(e),
                }
            )
            
    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task. Override in subclasses.
        
        Args:
            task: Dictionary containing task details
            
        Returns:
            Dictionary containing task results
        """
        pass
        
    async def handle_error(self, error: Exception, message: Optional[AgentMessage] = None):
        """Handle an error. Override for custom error handling."""
        print(f"[{self.agent_id}] Error: {error}")
        
        # Send error message
        await self.send_message(
            MessageType.ERROR,
            {
                "agent_id": self.agent_id,
                "error": str(error),
                "message": message.to_dict() if message else None,
            }
        )
        
    # Lifecycle hooks
    async def on_start(self):
        """Called when agent starts. Override in subclasses."""
        pass
        
    async def on_stop(self):
        """Called when agent stops. Override in subclasses."""
        pass
        
    async def on_pause(self):
        """Called when agent is paused. Override in subclasses."""
        pass
        
    async def on_resume(self):
        """Called when agent is resumed. Override in subclasses."""
        pass
        
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "agent_id": self.agent_id,
            "state": self.state.name,
            "metrics": {
                "messages_processed": self.metrics.messages_processed,
                "messages_sent": self.metrics.messages_sent,
                "errors": self.metrics.errors,
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "last_active": self.metrics.last_active.isoformat() if self.metrics.last_active else None,
                "avg_processing_time_ms": self.metrics.avg_processing_time_ms,
            },
            "state_history": [
                {
                    "timestamp": ts.isoformat(),
                    "from": old,
                    "to": new,
                    "reason": reason
                }
                for ts, old, new, reason in self.state_history[-10:]
            ],
        }
