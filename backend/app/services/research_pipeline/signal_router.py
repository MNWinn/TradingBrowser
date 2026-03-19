"""
Signal Router for TradingBrowser.

Routes research signals to appropriate agents with:
- Intelligent signal distribution
- Signal deduplication
- Priority-based routing
- Comprehensive signal logging
"""

import asyncio
import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Types of research signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"
    ALERT = "alert"
    RESEARCH_COMPLETE = "research_complete"
    MARKET_EVENT = "market_event"


class SignalPriority(str, Enum):
    """Signal priority levels."""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"          # Process ASAP
    MEDIUM = "medium"      # Normal processing
    LOW = "low"            # Background processing


class AgentType(str, Enum):
    """Types of agents that can receive signals."""
    TRADING = "trading"
    RISK = "risk"
    RESEARCH = "research"
    NOTIFICATION = "notification"
    COMPLIANCE = "compliance"
    JOURNAL = "journal"


@dataclass
class Signal:
    """Represents a research signal."""
    signal_id: str
    ticker: str
    signal_type: SignalType
    priority: SignalPriority
    source: str  # e.g., "swarm", "market_watch", "manual"
    data: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiry: Optional[datetime] = None
    routed_to: list[str] = field(default_factory=list)
    processed: bool = False
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "signal_type": self.signal_type.value,
            "priority": self.priority.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "routed_to": self.routed_to,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        return cls(
            signal_id=data["signal_id"],
            ticker=data["ticker"],
            signal_type=SignalType(data["signal_type"]),
            priority=SignalPriority(data["priority"]),
            source=data["source"],
            data=data.get("data", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(timezone.utc),
            expiry=datetime.fromisoformat(data["expiry"]) if data.get("expiry") else None,
            routed_to=data.get("routed_to", []),
            processed=data.get("processed", False),
            processed_at=datetime.fromisoformat(data["processed_at"]) if data.get("processed_at") else None,
        )
    
    def get_dedup_key(self) -> str:
        """Generate a deduplication key for this signal."""
        # Create a key based on ticker, type, and key data elements
        key_data = f"{self.ticker}:{self.signal_type.value}:{self.source}"
        if "recommendation" in self.data:
            key_data += f":{self.data['recommendation']}"
        if "confidence" in self.data:
            # Round confidence to reduce noise
            conf = round(self.data["confidence"] * 10) / 10
            key_data += f":{conf}"
        
        return hashlib.md5(key_data.encode()).hexdigest()[:16]


@dataclass
class RoutingRule:
    """Defines a signal routing rule."""
    rule_id: str
    signal_types: list[SignalType]
    priorities: list[SignalPriority]
    tickers: Optional[list[str]] = None  # None = all tickers
    sources: Optional[list[str]] = None  # None = all sources
    target_agents: list[AgentType] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)  # Additional conditions
    enabled: bool = True
    
    def matches(self, signal: Signal) -> bool:
        """Check if this rule matches a signal."""
        if not self.enabled:
            return False
        
        if signal.signal_type not in self.signal_types:
            return False
        
        if signal.priority not in self.priorities:
            return False
        
        if self.tickers and signal.ticker not in self.tickers:
            return False
        
        if self.sources and signal.source not in self.sources:
            return False
        
        # Check additional conditions
        for key, value in self.conditions.items():
            if key not in signal.data or signal.data[key] != value:
                return False
        
        return True


class SignalRouter:
    """
    Intelligent signal routing system.
    
    Features:
    - Route signals to appropriate agents based on rules
    - Deduplicate signals to prevent noise
    - Priority-based routing
    - Comprehensive signal logging and audit trail
    """
    
    # Redis key prefixes
    SIGNAL_QUEUE_KEY = "router:signal_queue"
    SIGNAL_DATA_PREFIX = "router:signal:{signal_id}"
    DEDUP_KEY_PREFIX = "router:dedup:{dedup_key}"
    ROUTING_LOG_KEY = "router:log"
    AGENT_QUEUES = {
        AgentType.TRADING: "router:queue:trading",
        AgentType.RISK: "router:queue:risk",
        AgentType.RESEARCH: "router:queue:research",
        AgentType.NOTIFICATION: "router:queue:notification",
        AgentType.COMPLIANCE: "router:queue:compliance",
        AgentType.JOURNAL: "router:queue:journal",
    }
    ROUTING_RULES_KEY = "router:rules"
    SIGNAL_STATS_KEY = "router:stats"
    
    # Configuration
    DEDUP_WINDOW_SECONDS = 300  # 5 minutes
    MAX_LOG_ENTRIES = 10000
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._router_task: Optional[asyncio.Task] = None
        self._routing_rules: list[RoutingRule] = []
        self._subscribers: list[Callable[[Signal], Coroutine]] = []
        self._signal_history: deque = deque(maxlen=1000)
        
    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def initialize(self) -> None:
        """Initialize the signal router."""
        await self.redis.ping()
        self._running = True
        
        # Load routing rules
        await self._load_routing_rules()
        
        # Add default rules if none exist
        if not self._routing_rules:
            await self._add_default_routing_rules()
        
        # Start router task
        self._router_task = asyncio.create_task(self._routing_loop())
        
        logger.info(f"SignalRouter initialized with {len(self._routing_rules)} routing rules")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the signal router."""
        self._running = False
        self._shutdown_event.set()
        
        if self._router_task:
            self._router_task.cancel()
            try:
                await self._router_task
            except asyncio.CancelledError:
                pass
        
        await self._save_routing_rules()
        logger.info("SignalRouter shutdown complete")
    
    async def route_signal(
        self,
        ticker: str,
        signal_type: SignalType,
        priority: SignalPriority,
        source: str,
        data: dict,
        expiry: Optional[datetime] = None,
    ) -> Optional[Signal]:
        """
        Route a new signal through the system.
        
        Args:
            ticker: Stock ticker symbol
            signal_type: Type of signal
            priority: Signal priority
            source: Signal source
            data: Signal data
            expiry: Optional expiry time
            
        Returns:
            The created Signal if routed, None if deduplicated
        """
        import uuid
        
        signal = Signal(
            signal_id=f"sig-{uuid.uuid4().hex[:12]}",
            ticker=ticker.upper(),
            signal_type=signal_type,
            priority=priority,
            source=source,
            data=data,
            expiry=expiry,
        )
        
        # Check for duplicates
        if await self._is_duplicate(signal):
            logger.debug(f"Signal {signal.signal_id} deduplicated")
            return None
        
        # Save signal
        await self._save_signal(signal)
        
        # Add to priority queue
        priority_score = self._priority_to_score(priority)
        await self.redis.zadd(self.SIGNAL_QUEUE_KEY, {signal.signal_id: priority_score})
        
        # Mark as dedup
        await self._mark_dedup(signal)
        
        # Log routing
        await self._log_signal(signal, "received")
        
        logger.info(f"Signal {signal.signal_id} received: {signal_type.value} for {ticker}")
        return signal
    
    async def add_routing_rule(
        self,
        signal_types: list[SignalType],
        priorities: list[SignalPriority],
        target_agents: list[AgentType],
        tickers: Optional[list[str]] = None,
        sources: Optional[list[str]] = None,
        conditions: Optional[dict] = None,
    ) -> RoutingRule:
        """Add a new routing rule."""
        import uuid
        
        rule = RoutingRule(
            rule_id=f"rule-{uuid.uuid4().hex[:8]}",
            signal_types=signal_types,
            priorities=priorities,
            tickers=tickers,
            sources=sources,
            target_agents=target_agents,
            conditions=conditions or {},
        )
        
        self._routing_rules.append(rule)
        await self._save_routing_rules()
        
        logger.info(f"Added routing rule {rule.rule_id}")
        return rule
    
    async def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        for i, rule in enumerate(self._routing_rules):
            if rule.rule_id == rule_id:
                self._routing_rules.pop(i)
                await self._save_routing_rules()
                logger.info(f"Removed routing rule {rule_id}")
                return True
        return False
    
    async def get_routing_rules(self) -> list[dict]:
        """Get all routing rules."""
        return [
            {
                "rule_id": r.rule_id,
                "signal_types": [s.value for s in r.signal_types],
                "priorities": [p.value for p in r.priorities],
                "tickers": r.tickers,
                "sources": r.sources,
                "target_agents": [a.value for a in r.target_agents],
                "conditions": r.conditions,
                "enabled": r.enabled,
            }
            for r in self._routing_rules
        ]
    
    async def get_signal_log(
        self,
        ticker: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get signal routing log."""
        logs = await self.redis.lrange(self.ROUTING_LOG_KEY, 0, limit - 1)
        result = []
        
        for log_json in logs:
            log_entry = json.loads(log_json)
            if ticker and log_entry.get("ticker") != ticker.upper():
                continue
            if signal_type and log_entry.get("signal_type") != signal_type.value:
                continue
            result.append(log_entry)
        
        return result
    
    async def get_signal_stats(self) -> dict:
        """Get signal routing statistics."""
        stats_data = await self.redis.get(self.SIGNAL_STATS_KEY)
        if stats_data:
            return json.loads(stats_data)
        
        return {
            "total_signals": 0,
            "routed_signals": 0,
            "deduplicated_signals": 0,
            "by_type": {},
            "by_priority": {},
            "by_agent": {},
        }
    
    async def subscribe(self, callback: Callable[[Signal], Coroutine]) -> None:
        """Subscribe to routed signals."""
        self._subscribers.append(callback)
    
    async def unsubscribe(self, callback: Callable[[Signal], Coroutine]) -> None:
        """Unsubscribe from routed signals."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def acknowledge_signal(self, signal_id: str, agent_type: AgentType) -> bool:
        """Acknowledge signal processing by an agent."""
        signal_data = await self.redis.get(self.SIGNAL_DATA_PREFIX.format(signal_id=signal_id))
        if not signal_data:
            return False
        
        signal = Signal.from_dict(json.loads(signal_data))
        
        if agent_type.value not in signal.routed_to:
            signal.routed_to.append(agent_type.value)
        
        await self._save_signal(signal)
        await self._log_signal(signal, f"acknowledged_by_{agent_type.value}")
        
        return True
    
    async def _routing_loop(self) -> None:
        """Main routing loop."""
        while self._running:
            try:
                # Get highest priority signal
                signal_ids = await self.redis.zrange(self.SIGNAL_QUEUE_KEY, 0, 0)
                if not signal_ids:
                    await asyncio.sleep(0.1)
                    continue
                
                signal_id = signal_ids[0]
                
                # Remove from queue
                removed = await self.redis.zrem(self.SIGNAL_QUEUE_KEY, signal_id)
                if removed:
                    await self._process_signal(signal_id)
                
            except Exception as e:
                logger.exception(f"Error in routing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_signal(self, signal_id: str) -> None:
        """Process and route a signal."""
        signal_data = await self.redis.get(self.SIGNAL_DATA_PREFIX.format(signal_id=signal_id))
        if not signal_data:
            logger.warning(f"Signal {signal_id} not found")
            return
        
        signal = Signal.from_dict(json.loads(signal_data))
        
        try:
            # Check expiry
            if signal.expiry and datetime.now(timezone.utc) > signal.expiry:
                await self._log_signal(signal, "expired")
                logger.debug(f"Signal {signal_id} expired")
                return
            
            # Find matching routing rules
            routed = False
            for rule in self._routing_rules:
                if rule.matches(signal):
                    for agent_type in rule.target_agents:
                        await self._route_to_agent(signal, agent_type)
                        routed = True
            
            # If no rules matched, route to default agents based on priority
            if not routed:
                await self._default_routing(signal)
            
            signal.processed = True
            signal.processed_at = datetime.now(timezone.utc)
            await self._save_signal(signal)
            
            await self._update_stats("routed", signal)
            await self._log_signal(signal, "routed")
            
            # Notify subscribers
            for callback in self._subscribers:
                try:
                    await callback(signal)
                except Exception as e:
                    logger.error(f"Error notifying subscriber: {e}")
            
            self._signal_history.append(signal)
            
        except Exception as e:
            logger.exception(f"Error processing signal {signal_id}: {e}")
            await self._update_stats("error", signal)
    
    async def _route_to_agent(self, signal: Signal, agent_type: AgentType) -> None:
        """Route signal to a specific agent queue."""
        queue_key = self.AGENT_QUEUES.get(agent_type)
        if not queue_key:
            logger.warning(f"Unknown agent type: {agent_type}")
            return
        
        # Add to agent queue
        await self.redis.lpush(queue_key, signal.signal_id)
        
        # Trim queue if needed
        await self.redis.ltrim(queue_key, 0, 9999)
        
        if agent_type.value not in signal.routed_to:
            signal.routed_to.append(agent_type.value)
        
        logger.debug(f"Routed signal {signal.signal_id} to {agent_type.value}")
    
    async def _default_routing(self, signal: Signal) -> None:
        """Default routing when no rules match."""
        # Route based on signal type and priority
        if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
            await self._route_to_agent(signal, AgentType.TRADING)
            await self._route_to_agent(signal, AgentType.RISK)
        
        if signal.priority in [SignalPriority.CRITICAL, SignalPriority.HIGH]:
            await self._route_to_agent(signal, AgentType.NOTIFICATION)
        
        if signal.signal_type == SignalType.RESEARCH_COMPLETE:
            await self._route_to_agent(signal, AgentType.JOURNAL)
        
        # Always route to research for tracking
        await self._route_to_agent(signal, AgentType.RESEARCH)
    
    async def _is_duplicate(self, signal: Signal) -> bool:
        """Check if signal is a duplicate."""
        dedup_key = signal.get_dedup_key()
        exists = await self.redis.exists(self.DEDUP_KEY_PREFIX.format(dedup_key=dedup_key))
        return bool(exists)
    
    async def _mark_dedup(self, signal: Signal) -> None:
        """Mark signal for deduplication."""
        dedup_key = signal.get_dedup_key()
        await self.redis.setex(
            self.DEDUP_KEY_PREFIX.format(dedup_key=dedup_key),
            self.DEDUP_WINDOW_SECONDS,
            signal.signal_id
        )
    
    async def _save_signal(self, signal: Signal) -> None:
        """Save signal to Redis."""
        await self.redis.setex(
            self.SIGNAL_DATA_PREFIX.format(signal_id=signal.signal_id),
            86400,  # 24 hour TTL
            json.dumps(signal.to_dict())
        )
    
    async def _log_signal(self, signal: Signal, action: str) -> None:
        """Log signal routing event."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal.signal_id,
            "ticker": signal.ticker,
            "signal_type": signal.signal_type.value,
            "priority": signal.priority.value,
            "source": signal.source,
            "action": action,
            "routed_to": signal.routed_to,
        }
        
        await self.redis.lpush(self.ROUTING_LOG_KEY, json.dumps(log_entry))
        await self.redis.ltrim(self.ROUTING_LOG_KEY, 0, self.MAX_LOG_ENTRIES - 1)
    
    async def _update_stats(self, event_type: str, signal: Signal) -> None:
        """Update routing statistics."""
        stats = await self.get_signal_stats()
        
        if event_type == "routed":
            stats["routed_signals"] = stats.get("routed_signals", 0) + 1
        elif event_type == "deduplicated":
            stats["deduplicated_signals"] = stats.get("deduplicated_signals", 0) + 1
        
        stats["total_signals"] = stats.get("total_signals", 0) + 1
        
        # By type
        type_key = signal.signal_type.value
        stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1
        
        # By priority
        priority_key = signal.priority.value
        stats["by_priority"][priority_key] = stats["by_priority"].get(priority_key, 0) + 1
        
        # By agent
        for agent in signal.routed_to:
            stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
        
        await self.redis.setex(
            self.SIGNAL_STATS_KEY,
            86400 * 7,  # 7 days
            json.dumps(stats)
        )
    
    def _priority_to_score(self, priority: SignalPriority) -> int:
        """Convert priority to queue score (lower = higher priority)."""
        scores = {
            SignalPriority.CRITICAL: 1,
            SignalPriority.HIGH: 2,
            SignalPriority.MEDIUM: 3,
            SignalPriority.LOW: 4,
        }
        return scores.get(priority, 5)
    
    async def _add_default_routing_rules(self) -> None:
        """Add default routing rules."""
        # Critical alerts go to all agents
        await self.add_routing_rule(
            signal_types=[SignalType.ALERT, SignalType.BUY, SignalType.SELL],
            priorities=[SignalPriority.CRITICAL],
            target_agents=[AgentType.TRADING, AgentType.RISK, AgentType.NOTIFICATION, AgentType.COMPLIANCE],
        )
        
        # High priority trading signals
        await self.add_routing_rule(
            signal_types=[SignalType.BUY, SignalType.SELL],
            priorities=[SignalPriority.HIGH],
            target_agents=[AgentType.TRADING, AgentType.RISK],
        )
        
        # Research completion
        await self.add_routing_rule(
            signal_types=[SignalType.RESEARCH_COMPLETE],
            priorities=[SignalPriority.MEDIUM, SignalPriority.HIGH],
            target_agents=[AgentType.RESEARCH, AgentType.JOURNAL],
        )
        
        # Market events
        await self.add_routing_rule(
            signal_types=[SignalType.MARKET_EVENT],
            priorities=[SignalPriority.HIGH, SignalPriority.MEDIUM],
            target_agents=[AgentType.NOTIFICATION, AgentType.RESEARCH],
        )
    
    async def _load_routing_rules(self) -> None:
        """Load routing rules from Redis."""
        rules_data = await self.redis.get(self.ROUTING_RULES_KEY)
        if rules_data:
            try:
                rules_list = json.loads(rules_data)
                for rule_data in rules_list:
                    rule = RoutingRule(
                        rule_id=rule_data["rule_id"],
                        signal_types=[SignalType(s) for s in rule_data["signal_types"]],
                        priorities=[SignalPriority(p) for p in rule_data["priorities"]],
                        tickers=rule_data.get("tickers"),
                        sources=rule_data.get("sources"),
                        target_agents=[AgentType(a) for a in rule_data["target_agents"]],
                        conditions=rule_data.get("conditions", {}),
                        enabled=rule_data.get("enabled", True),
                    )
                    self._routing_rules.append(rule)
            except Exception as e:
                logger.error(f"Error loading routing rules: {e}")
    
    async def _save_routing_rules(self) -> None:
        """Save routing rules to Redis."""
        rules_data = [
            {
                "rule_id": r.rule_id,
                "signal_types": [s.value for s in r.signal_types],
                "priorities": [p.value for p in r.priorities],
                "tickers": r.tickers,
                "sources": r.sources,
                "target_agents": [a.value for a in r.target_agents],
                "conditions": r.conditions,
                "enabled": r.enabled,
            }
            for r in self._routing_rules
        ]
        
        await self.redis.setex(
            self.ROUTING_RULES_KEY,
            86400 * 30,  # 30 days
            json.dumps(rules_data)
        )


# Global router instance
_router: Optional[SignalRouter] = None


async def get_router() -> SignalRouter:
    """Get or create the global signal router."""
    global _router
    if _router is None:
        _router = SignalRouter()
        await _router.initialize()
    return _router


async def shutdown_router() -> None:
    """Shutdown the global signal router."""
    global _router
    if _router:
        await _router.shutdown()
        _router = None


# Convenience functions for routing signals

async def route_buy_signal(
    ticker: str,
    source: str,
    confidence: float,
    data: dict,
    priority: SignalPriority = SignalPriority.HIGH,
) -> Optional[Signal]:
    """Route a buy signal."""
    router = await get_router()
    return await router.route_signal(
        ticker=ticker,
        signal_type=SignalType.BUY,
        priority=priority,
        source=source,
        data={"confidence": confidence, **data},
    )


async def route_sell_signal(
    ticker: str,
    source: str,
    confidence: float,
    data: dict,
    priority: SignalPriority = SignalPriority.HIGH,
) -> Optional[Signal]:
    """Route a sell signal."""
    router = await get_router()
    return await router.route_signal(
        ticker=ticker,
        signal_type=SignalType.SELL,
        priority=priority,
        source=source,
        data={"confidence": confidence, **data},
    )


async def route_alert(
    ticker: str,
    source: str,
    message: str,
    severity: str,
    data: dict,
    priority: SignalPriority = SignalPriority.MEDIUM,
) -> Optional[Signal]:
    """Route an alert signal."""
    router = await get_router()
    return await router.route_signal(
        ticker=ticker,
        signal_type=SignalType.ALERT,
        priority=priority,
        source=source,
        data={"message": message, "severity": severity, **data},
    )
