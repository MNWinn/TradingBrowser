"""
Supervisor Agent

Orchestrates all sub-agents.
Assigns tasks and resolves disagreements.
Escalates uncertainty and maintains operational discipline.

Outputs:
- System state
- Research priorities
- Daily summary
- Next actions
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
import asyncio
import json

from .base_agent import BaseAgent, AgentState
from .message_bus import MessageType, AgentMessage, get_message_bus


class SystemMode(Enum):
    """Operating mode of the trading system."""
    RESEARCH = "research"  # Hypothesis testing phase
    PAPER = "paper"  # Paper trading validation
    LIVE = "live"  # Live trading
    PAUSED = "paused"  # Trading paused
    EMERGENCY = "emergency"  # Emergency stop


class Priority(Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class AgentStatus:
    """Status of a sub-agent."""
    agent_id: str
    state: str
    last_heartbeat: datetime
    metrics: Dict[str, Any]
    current_task: Optional[str]
    errors_count: int = 0


@dataclass
class Disagreement:
    """A disagreement between agents."""
    disagreement_id: str
    timestamp: datetime
    agents_involved: List[str]
    topic: str
    conflicting_opinions: Dict[str, Any]
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass
class ResearchPriority:
    """A research priority item."""
    priority_id: str
    description: str
    priority_level: Priority
    assigned_agent: Optional[str]
    created_at: datetime
    deadline: Optional[datetime]
    status: str = "pending"  # pending, in_progress, completed, cancelled
    related_hypotheses: List[str] = field(default_factory=list)


@dataclass
class DailySummary:
    """Daily system summary."""
    date: datetime
    
    # Activity
    trades_executed: int
    trades_proposed: int
    trades_rejected: int
    
    # Performance
    daily_pnl: float
    win_rate: float
    avg_trade_return: float
    
    # Research
    hypotheses_tested: int
    hypotheses_validated: int
    hypotheses_rejected: int
    
    # Agent health
    agent_statuses: Dict[str, str]
    errors_logged: int
    
    # Key events
    regime_changes: List[Dict]
    significant_lessons: List[str]
    
    # Priorities for tomorrow
    next_actions: List[str]


@dataclass
class SystemState:
    """Complete system state snapshot."""
    timestamp: datetime
    mode: SystemMode
    
    # Agent states
    agent_states: Dict[str, AgentStatus]
    
    # Active operations
    active_trades: int
    pending_proposals: int
    running_research: int
    
    # Health
    system_health: str  # healthy, degraded, critical
    last_error: Optional[str]
    error_count_24h: int
    
    # Performance
    total_trades: int
    total_pnl: float
    current_drawdown: float


class SupervisorAgent(BaseAgent):
    """
    Supervisor agent that orchestrates the entire trading research system.
    """
    
    def __init__(self, message_bus=None, config=None):
        super().__init__("supervisor", message_bus, config)
        
        # Configuration
        self.heartbeat_interval_sec = config.get("heartbeat_interval", 30) if config else 30
        self.summary_interval_hours = config.get("summary_interval", 24) if config else 24
        self.max_disagreements = config.get("max_disagreements", 10) if config else 10
        
        # System state
        self._mode = SystemMode.RESEARCH
        self._agent_statuses: Dict[str, AgentStatus] = {}
        self._disagreements: List[Disagreement] = []
        self._research_priorities: List[ResearchPriority] = []
        self._daily_summaries: List[DailySummary] = []
        
        # Agent registry
        self._registered_agents: Set[str] = set()
        
        # Task queue
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # System metrics
        self._total_trades = 0
        self._total_pnl = 0.0
        self._errors_24h = 0
        self._last_summary_time = datetime.utcnow()
        
        # Register handlers
        self.register_handler(MessageType.AGENT_STATUS, self._handle_agent_status)
        self.register_handler(MessageType.ERROR, self._handle_error)
        self.register_handler(MessageType.TRADE_PROPOSAL, self._handle_trade_proposal)
        self.register_handler(MessageType.TRADE_APPROVED, self._handle_trade_approved)
        self.register_handler(MessageType.TRADE_REJECTED, self._handle_trade_rejected)
        self.register_handler(MessageType.DISAGREEMENT, self._handle_disagreement)
        self.register_handler(MessageType.ESCALATION, self._handle_escalation)
        
    async def on_start(self):
        """Start supervisor loops."""
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._summary_loop())
        asyncio.create_task(self._task_dispatcher_loop())
        
    async def _heartbeat_loop(self):
        """Monitor agent health."""
        while self._running and self.state.value == "RUNNING":
            try:
                await self._check_agent_health()
                await asyncio.sleep(self.heartbeat_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Heartbeat loop error: {e}")
                await asyncio.sleep(self.heartbeat_interval_sec)
                
    async def _summary_loop(self):
        """Generate periodic summaries."""
        while self._running and self.state.value == "RUNNING":
            try:
                await asyncio.sleep(self.summary_interval_hours * 3600)
                await self._generate_daily_summary()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Summary loop error: {e}")
                
    async def _task_dispatcher_loop(self):
        """Dispatch tasks to agents."""
        while self._running and self.state.value == "RUNNING":
            try:
                priority, timestamp, task = await self._task_queue.get()
                await self._dispatch_task(task)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.agent_id}] Task dispatcher error: {e}")
                
    async def _check_agent_health(self):
        """Check health of all registered agents."""
        now = datetime.utcnow()
        
        for agent_id, status in self._agent_statuses.items():
            time_since_heartbeat = (now - status.last_heartbeat).total_seconds()
            
            if time_since_heartbeat > self.heartbeat_interval_sec * 3:
                # Agent may be unresponsive
                status.state = "unresponsive"
                await self._handle_unresponsive_agent(agent_id)
                
            if status.errors_count > 10:
                # Agent has too many errors
                await self._handle_erroring_agent(agent_id)
                
    async def _handle_unresponsive_agent(self, agent_id: str):
        """Handle an unresponsive agent."""
        print(f"[SUPERVISOR] Agent {agent_id} is unresponsive")
        
        # Publish alert
        await self.send_message(
            MessageType.ESCALATION,
            {
                "escalation_type": "unresponsive_agent",
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "high",
            },
            priority=1
        )
        
    async def _handle_erroring_agent(self, agent_id: str):
        """Handle an agent with many errors."""
        print(f"[SUPERVISOR] Agent {agent_id} has excessive errors")
        
        # Publish alert
        await self.send_message(
            MessageType.ESCALATION,
            {
                "escalation_type": "erroring_agent",
                "agent_id": agent_id,
                "error_count": self._agent_statuses[agent_id].errors_count,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "critical",
            },
            priority=1
        )
        
    async def _handle_agent_status(self, message: AgentMessage):
        """Handle agent status updates."""
        payload = message.payload
        agent_id = payload.get("agent_id")
        
        if agent_id:
            if agent_id not in self._agent_statuses:
                self._registered_agents.add(agent_id)
                
            self._agent_statuses[agent_id] = AgentStatus(
                agent_id=agent_id,
                state=payload.get("state", "unknown"),
                last_heartbeat=datetime.utcnow(),
                metrics=payload.get("metrics", {}),
                current_task=payload.get("task_id"),
                errors_count=payload.get("errors", 0),
            )
            
    async def _handle_error(self, message: AgentMessage):
        """Handle error messages."""
        payload = message.payload
        agent_id = payload.get("agent_id")
        error = payload.get("error")
        
        self._errors_24h += 1
        
        if agent_id and agent_id in self._agent_statuses:
            self._agent_statuses[agent_id].errors_count += 1
            
        # Check if we need to escalate
        if self._errors_24h > 20:
            await self._escalate_system_issue("Excessive errors across system")
            
    async def _handle_trade_proposal(self, message: AgentMessage):
        """Handle trade proposals."""
        payload = message.payload
        
        # Log proposal
        print(f"[SUPERVISOR] Trade proposal: {payload.get('ticker')} {payload.get('direction')}")
        
        # In research mode, we might want to auto-reject or queue for analysis
        if self._mode == SystemMode.RESEARCH:
            # Allow through for testing
            pass
        elif self._mode == SystemMode.PAUSED:
            # Auto-reject
            await self.send_message(
                MessageType.TRADE_REJECTED,
                {
                    "proposal_id": payload.get("proposal_id"),
                    "reason": "System paused",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            
    async def _handle_trade_approved(self, message: AgentMessage):
        """Handle approved trades."""
        self._total_trades += 1
        
    async def _handle_trade_rejected(self, message: AgentMessage):
        """Handle rejected trades."""
        # Log for analysis
        pass
        
    async def _handle_disagreement(self, message: AgentMessage):
        """Handle disagreements between agents."""
        payload = message.payload
        
        disagreement = Disagreement(
            disagreement_id=f"disagree_{datetime.utcnow().timestamp()}",
            timestamp=datetime.utcnow(),
            agents_involved=payload.get("agents", []),
            topic=payload.get("topic", ""),
            conflicting_opinions=payload.get("opinions", {}),
        )
        
        self._disagreements.append(disagreement)
        
        # Try to resolve
        resolution = await self._resolve_disagreement(disagreement)
        if resolution:
            disagreement.resolution = resolution
            disagreement.resolved_at = datetime.utcnow()
            
    async def _resolve_disagreement(self, disagreement: Disagreement) -> Optional[str]:
        """Attempt to resolve a disagreement."""
        
        # Simple resolution logic - could be more sophisticated
        opinions = disagreement.conflicting_opinions
        
        if len(opinions) == 2:
            # Check if we can weight by agent confidence
            # For now, default to more conservative option
            return "conservative"
            
        return None
        
    async def _handle_escalation(self, message: AgentMessage):
        """Handle escalations."""
        payload = message.payload
        escalation_type = payload.get("escalation_type")
        severity = payload.get("severity", "medium")
        
        print(f"[SUPERVISOR] Escalation: {escalation_type} (severity: {severity})")
        
        if severity == "critical":
            # Consider pausing system
            if self._mode != SystemMode.EMERGENCY:
                await self.set_mode(SystemMode.PAUSED)
                
    async def _escalate_system_issue(self, reason: str):
        """Escalate a system-wide issue."""
        await self.send_message(
            MessageType.ESCALATION,
            {
                "escalation_type": "system_issue",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "critical",
            },
            priority=1
        )
        
    async def _dispatch_task(self, task: Dict[str, Any]):
        """Dispatch a task to appropriate agent."""
        target_agent = task.get("target_agent")
        
        if target_agent and target_agent in self._registered_agents:
            await self.send_message(
                MessageType.TASK_ASSIGNMENT,
                {
                    "task": task,
                    "assigned_by": self.agent_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                target=target_agent
            )
            
    async def assign_task(
        self, 
        target_agent: str, 
        task: Dict[str, Any], 
        priority: Priority = Priority.MEDIUM
    ):
        """Assign a task to an agent."""
        task["target_agent"] = target_agent
        await self._task_queue.put((priority.value, datetime.utcnow().timestamp(), task))
        
    async def set_mode(self, mode: SystemMode):
        """Set system operating mode."""
        old_mode = self._mode
        self._mode = mode
        
        print(f"[SUPERVISOR] Mode changed: {old_mode.value} -> {mode.value}")
        
        # Notify all agents
        await self.send_message(
            MessageType.SYSTEM_STATE,
            {
                "mode": mode.value,
                "previous_mode": old_mode.value,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": "supervisor_command",
            }
        )
        
    async def register_agent(self, agent_id: str):
        """Register an agent with the supervisor."""
        self._registered_agents.add(agent_id)
        self._agent_statuses[agent_id] = AgentStatus(
            agent_id=agent_id,
            state="registered",
            last_heartbeat=datetime.utcnow(),
            metrics={},
            current_task=None,
        )
        print(f"[SUPERVISOR] Agent registered: {agent_id}")
        
    async def _generate_daily_summary(self) -> DailySummary:
        """Generate daily summary."""
        
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        summary = DailySummary(
            date=now,
            trades_executed=0,  # Would count from history
            trades_proposed=0,
            trades_rejected=0,
            daily_pnl=0.0,
            win_rate=0.0,
            avg_trade_return=0.0,
            hypotheses_tested=0,
            hypotheses_validated=0,
            hypotheses_rejected=0,
            agent_statuses={aid: status.state for aid, status in self._agent_statuses.items()},
            errors_logged=self._errors_24h,
            regime_changes=[],
            significant_lessons=[],
            next_actions=self._generate_next_actions(),
        )
        
        self._daily_summaries.append(summary)
        self._last_summary_time = now
        self._errors_24h = 0  # Reset error count
        
        # Publish summary
        await self.send_message(
            MessageType.SYSTEM_STATE,
            {
                "type": "daily_summary",
                "date": now.isoformat(),
                "summary": {
                    "trades_executed": summary.trades_executed,
                    "daily_pnl": summary.daily_pnl,
                    "agent_health": summary.agent_statuses,
                    "errors_24h": summary.errors_logged,
                },
                "next_actions": summary.next_actions,
            }
        )
        
        return summary
        
    def _generate_next_actions(self) -> List[str]:
        """Generate list of next actions based on system state."""
        actions = []
        
        # Check for research priorities
        pending_research = [p for p in self._research_priorities if p.status == "pending"]
        if pending_research:
            actions.append(f"Process {len(pending_research)} pending research priorities")
            
        # Check agent health
        unhealthy = [aid for aid, status in self._agent_statuses.items() if status.state != "running"]
        if unhealthy:
            actions.append(f"Address {len(unhealthy)} unhealthy agents: {', '.join(unhealthy)}")
            
        # Check for unvalidated hypotheses
        actions.append("Review recent trade performance for pattern insights")
        
        # Check graduation candidates
        actions.append("Check evaluation scorecards for graduation candidates")
        
        return actions
        
    def get_system_state(self) -> SystemState:
        """Get current system state."""
        return SystemState(
            timestamp=datetime.utcnow(),
            mode=self._mode,
            agent_states=self._agent_statuses,
            active_trades=0,  # Would query execution agent
            pending_proposals=0,
            running_research=sum(1 for p in self._research_priorities if p.status == "in_progress"),
            system_health=self._calculate_system_health(),
            last_error=None,
            error_count_24h=self._errors_24h,
            total_trades=self._total_trades,
            total_pnl=self._total_pnl,
            current_drawdown=0.0,
        )
        
    def _calculate_system_health(self) -> str:
        """Calculate overall system health."""
        if not self._agent_statuses:
            return "unknown"
            
        running = sum(1 for s in self._agent_statuses.values() if s.state == "running")
        total = len(self._agent_statuses)
        
        if running == total:
            return "healthy"
        elif running >= total * 0.7:
            return "degraded"
        else:
            return "critical"
            
    async def add_research_priority(
        self, 
        description: str, 
        priority: Priority = Priority.MEDIUM,
        deadline: Optional[datetime] = None
    ) -> str:
        """Add a research priority."""
        
        priority_id = f"priority_{datetime.utcnow().timestamp()}"
        
        rp = ResearchPriority(
            priority_id=priority_id,
            description=description,
            priority_level=priority,
            assigned_agent=None,
            created_at=datetime.utcnow(),
            deadline=deadline,
        )
        
        self._research_priorities.append(rp)
        
        return priority_id
        
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task assignment."""
        task_type = task.get("type")
        
        if task_type == "set_mode":
            mode_str = task.get("mode", "research")
            mode = SystemMode(mode_str)
            await self.set_mode(mode)
            return {"status": "mode_changed", "new_mode": mode.value}
            
        elif task_type == "get_system_state":
            state = self.get_system_state()
            return {
                "state": {
                    "timestamp": state.timestamp.isoformat(),
                    "mode": state.mode.value,
                    "system_health": state.system_health,
                    "agent_count": len(state.agent_states),
                    "total_trades": state.total_trades,
                    "error_count_24h": state.error_count_24h,
                }
            }
            
        elif task_type == "get_agent_statuses":
            return {
                "agents": [
                    {
                        "agent_id": status.agent_id,
                        "state": status.state,
                        "last_heartbeat": status.last_heartbeat.isoformat(),
                        "current_task": status.current_task,
                        "errors_count": status.errors_count,
                    }
                    for status in self._agent_statuses.values()
                ]
            }
            
        elif task_type == "assign_task":
            target = task.get("target_agent")
            task_data = task.get("task", {})
            priority = Priority(task.get("priority", 3))
            await self.assign_task(target, task_data, priority)
            return {"status": "task_queued", "target": target}
            
        elif task_type == "add_research_priority":
            description = task.get("description", "")
            priority = Priority(task.get("priority", 3))
            priority_id = await self.add_research_priority(description, priority)
            return {"priority_id": priority_id}
            
        elif task_type == "get_research_priorities":
            return {
                "priorities": [
                    {
                        "priority_id": p.priority_id,
                        "description": p.description,
                        "priority": p.priority_level.name,
                        "status": p.status,
                        "created_at": p.created_at.isoformat(),
                    }
                    for p in self._research_priorities
                ]
            }
            
        elif task_type == "get_daily_summaries":
            limit = task.get("limit", 7)
            return {
                "summaries": [
                    {
                        "date": s.date.isoformat(),
                        "trades_executed": s.trades_executed,
                        "daily_pnl": s.daily_pnl,
                        "errors_logged": s.errors_logged,
                        "next_actions": s.next_actions,
                    }
                    for s in self._daily_summaries[-limit:]
                ]
            }
            
        elif task_type == "get_disagreements":
            return {
                "disagreements": [
                    {
                        "disagreement_id": d.disagreement_id,
                        "timestamp": d.timestamp.isoformat(),
                        "agents": d.agents_involved,
                        "topic": d.topic,
                        "resolution": d.resolution,
                    }
                    for d in self._disagreements[-20:]
                ]
            }
            
        return {"error": f"Unknown task type: {task_type}"}
        
    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        status = super().get_status()
        state = self.get_system_state()
        status.update({
            "system_mode": self._mode.value,
            "system_health": state.system_health,
            "registered_agents": list(self._registered_agents),
            "agent_count": len(self._agent_statuses),
            "disagreements_count": len(self._disagreements),
            "research_priorities_count": len(self._research_priorities),
            "daily_summaries_count": len(self._daily_summaries),
            "total_trades": self._total_trades,
            "errors_24h": self._errors_24h,
        })
        return status


import asyncio
