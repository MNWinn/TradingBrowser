"""
Message Bus for Inter-Agent Communication

Provides asynchronous pub/sub messaging between agents with typed messages.
"""

from enum import Enum, auto
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from collections import defaultdict
import json


class MessageType(Enum):
    """Types of messages that can be passed between agents."""
    # Market Data
    MARKET_STRUCTURE_UPDATE = auto()
    REGIME_CHANGE = auto()
    PRICE_ACTION_ALERT = auto()
    
    # MiroFish Signals
    MIROFISH_PREDICTION = auto()
    MIROFISH_SIGNAL_UPDATE = auto()
    
    # Research
    HYPOTHESIS_PROPOSED = auto()
    HYPOTHESIS_TESTED = auto()
    RESEARCH_RESULTS = auto()
    
    # Strategy
    TRADE_PROPOSAL = auto()
    STRATEGY_UPDATE = auto()
    SETUP_IDENTIFIED = auto()
    
    # Risk
    RISK_ASSESSMENT = auto()
    TRADE_APPROVED = auto()
    TRADE_REJECTED = auto()
    RISK_VIOLATION = auto()
    
    # Execution
    EXECUTION_FILL = auto()
    TRADE_OPENED = auto()
    TRADE_CLOSED = auto()
    PNL_UPDATE = auto()
    
    # Evaluation
    EVALUATION_COMPLETE = auto()
    SCORECARD_UPDATE = auto()
    ROBUSTNESS_METRICS = auto()
    
    # Memory/Learning
    LESSON_LEARNED = auto()
    PATTERN_DETECTED = auto()
    PRIOR_UPDATE = auto()
    
    # Supervisor
    TASK_ASSIGNMENT = auto()
    AGENT_STATUS = auto()
    SYSTEM_STATE = auto()
    DISAGREEMENT = auto()
    ESCALATION = auto()
    
    # System
    HEARTBEAT = auto()
    ERROR = auto()
    SHUTDOWN = auto()


@dataclass
class AgentMessage:
    """A message passed between agents."""
    msg_type: MessageType
    source: str  # Agent ID that sent the message
    target: Optional[str]  # Target agent ID (None for broadcast)
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    msg_id: str = field(default_factory=lambda: f"msg_{datetime.utcnow().timestamp()}")
    correlation_id: Optional[str] = None  # For request/response patterns
    priority: int = 5  # 1 = highest, 10 = lowest
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type.name,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create message from dictionary."""
        return cls(
            msg_id=data["msg_id"],
            msg_type=MessageType[data["msg_type"]],
            source=data["source"],
            target=data.get("target"),
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            priority=data.get("priority", 5),
        )


class MessageBus:
    """
    Asynchronous message bus for inter-agent communication.
    
    Features:
    - Pub/sub messaging with typed messages
    - Request/response patterns
    - Priority-based message handling
    - Message history and replay
    """
    
    def __init__(self, max_history: int = 10000):
        self.subscribers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self.agent_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.message_history: List[AgentMessage] = []
        self.max_history = max_history
        self._lock = asyncio.Lock()
        self._running = True
        self._message_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._handlers: Dict[str, asyncio.Task] = {}
        
    async def start(self):
        """Start the message bus processing loop."""
        self._running = True
        asyncio.create_task(self._process_loop())
        
    async def stop(self):
        """Stop the message bus."""
        self._running = False
        # Cancel all pending handlers
        for task in self._handlers.values():
            task.cancel()
        
    async def subscribe(self, msg_type: MessageType, callback: Callable):
        """Subscribe to a message type."""
        async with self._lock:
            self.subscribers[msg_type].append(callback)
            
    async def subscribe_to_agent(self, agent_id: str, callback: Callable):
        """Subscribe to messages targeted at a specific agent."""
        async with self._lock:
            self.agent_subscribers[agent_id].append(callback)
            
    async def unsubscribe(self, msg_type: MessageType, callback: Callable):
        """Unsubscribe from a message type."""
        async with self._lock:
            if callback in self.subscribers[msg_type]:
                self.subscribers[msg_type].remove(callback)
                
    async def publish(self, message: AgentMessage) -> bool:
        """
        Publish a message to the bus.
        
        Returns True if message was published successfully.
        """
        if not self._running:
            return False
            
        # Add to history
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
            
        # Add to processing queue with priority
        await self._message_queue.put((message.priority, message.timestamp.timestamp(), message))
        return True
        
    async def _process_loop(self):
        """Main processing loop for the message bus."""
        while self._running:
            try:
                _, _, message = await asyncio.wait_for(
                    self._message_queue.get(), 
                    timeout=1.0
                )
                await self._dispatch(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[MessageBus] Error processing message: {e}")
                
    async def _dispatch(self, message: AgentMessage):
        """Dispatch a message to all relevant subscribers."""
        tasks = []
        
        # Dispatch to type-based subscribers
        async with self._lock:
            callbacks = self.subscribers[message.msg_type].copy()
            
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(asyncio.create_task(callback(message)))
                else:
                    callback(message)
            except Exception as e:
                print(f"[MessageBus] Error in subscriber callback: {e}")
                
        # Dispatch to target agent subscribers
        if message.target:
            async with self._lock:
                agent_callbacks = self.agent_subscribers[message.target].copy()
                
            for callback in agent_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        tasks.append(asyncio.create_task(callback(message)))
                    else:
                        callback(message)
                except Exception as e:
                    print(f"[MessageBus] Error in agent subscriber callback: {e}")
                    
        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def request(
        self, 
        message: AgentMessage, 
        timeout_sec: float = 30.0
    ) -> Optional[AgentMessage]:
        """
        Send a request and wait for a response.
        
        Uses correlation_id to match request with response.
        """
        correlation_id = f"req_{datetime.utcnow().timestamp()}"
        message.correlation_id = correlation_id
        
        response_future = asyncio.Future()
        
        async def response_handler(msg: AgentMessage):
            if msg.correlation_id == correlation_id:
                if not response_future.done():
                    response_future.set_result(msg)
                    
        # Subscribe to responses
        await self.subscribe_to_agent(message.source, response_handler)
        
        try:
            # Publish the request
            await self.publish(message)
            
            # Wait for response with timeout
            return await asyncio.wait_for(response_future, timeout=timeout_sec)
        except asyncio.TimeoutError:
            return None
        finally:
            # Cleanup
            await self.unsubscribe(MessageType.AGENT_STATUS, response_handler)
            
    def get_history(
        self, 
        msg_type: Optional[MessageType] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AgentMessage]:
        """Get message history with optional filtering."""
        filtered = self.message_history
        
        if msg_type:
            filtered = [m for m in filtered if m.msg_type == msg_type]
        if source:
            filtered = [m for m in filtered if m.source == source]
        if since:
            filtered = [m for m in filtered if m.timestamp >= since]
            
        return filtered[-limit:]
        
    def clear_history(self):
        """Clear message history."""
        self.message_history = []
        
    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics."""
        return {
            "total_messages": len(self.message_history),
            "subscribers_by_type": {k.name: len(v) for k, v in self.subscribers.items()},
            "agent_subscribers": len(self.agent_subscribers),
            "queue_size": self._message_queue.qsize(),
            "running": self._running,
        }


# Global message bus instance
_global_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = MessageBus()
    return _global_bus


def reset_message_bus():
    """Reset the global message bus (useful for testing)."""
    global _global_bus
    _global_bus = MessageBus()
