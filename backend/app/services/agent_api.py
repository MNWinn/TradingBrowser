"""Agent-focused API service with bulk operations, agent-to-agent communication, and status broadcasting.

This module provides a comprehensive API for managing agents at scale, including:
- Bulk agent operations (start, stop, configure)
- Agent-to-agent communication endpoints
- Real-time status broadcasting via WebSocket
- Agent configuration management
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Body
from sqlalchemy import select, desc, update, delete
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.entities import (
    SwarmAgentRun,
    SwarmTask,
    AgentPerformanceStat,
    SwarmConsensusOutput,
    AgentInstance,
    AgentLog,
)
from app.services.audit import log_event

router = APIRouter(prefix="/agent-fleet", tags=["agent-fleet"])


# ============================================================================
# Enums and Constants
# ============================================================================

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    IDLE = "idle"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class AgentCommand(str, Enum):
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    RESTART = "restart"
    CONFIGURE = "configure"


# ============================================================================
# Pydantic Models
# ============================================================================

class AgentConfig(BaseModel):
    """Agent configuration model."""
    agent_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    priority: int = 5
    max_retries: int = 3
    timeout_seconds: int = 300
    tags: List[str] = Field(default_factory=list)


class AgentBulkOperation(BaseModel):
    """Bulk operation request model."""
    agent_names: List[str]
    command: AgentCommand
    config: Optional[AgentConfig] = None
    reason: Optional[str] = None


class AgentMessage(BaseModel):
    """Agent-to-agent message model."""
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    priority: int = Field(default=5, ge=1, le=10)
    ttl_seconds: int = Field(default=60, ge=10, le=3600)


class AgentBroadcast(BaseModel):
    """Broadcast message model."""
    sender: str
    message_type: str
    payload: Dict[str, Any]
    target_tags: Optional[List[str]] = None
    exclude_agents: Optional[List[str]] = None


class FleetStatus(BaseModel):
    """Fleet status response model."""
    total_agents: int
    running: int
    idle: int
    paused: int
    error: int
    stopped: int
    health_score: float
    last_updated: str


class AgentGroup(BaseModel):
    """Agent group model."""
    name: str
    description: Optional[str] = None
    agent_names: List[str]
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BatchOperationResult(BaseModel):
    """Batch operation result model."""
    operation_id: str
    command: str
    total: int
    succeeded: int
    failed: int
    results: List[Dict[str, Any]]
    started_at: str
    completed_at: Optional[str] = None


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class AgentFleetWebSocketManager:
    """Manages WebSocket connections for agent fleet operations."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.agent_subscriptions: Dict[str, List[WebSocket]] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the broadcast processor."""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._process_broadcasts())
    
    async def stop(self):
        """Stop the broadcast processor."""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None
    
    async def _process_broadcasts(self):
        """Process queued broadcast messages."""
        while True:
            try:
                message = await self.message_queue.get()
                await self._do_broadcast(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Broadcast error: {e}")
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from agent subscriptions
        for agent_name, connections in self.agent_subscriptions.items():
            if websocket in connections:
                connections.remove(websocket)
    
    def subscribe_to_agent(self, websocket: WebSocket, agent_name: str):
        """Subscribe a connection to agent-specific updates."""
        if agent_name not in self.agent_subscriptions:
            self.agent_subscriptions[agent_name] = []
        if websocket not in self.agent_subscriptions[agent_name]:
            self.agent_subscriptions[agent_name].append(websocket)
    
    def unsubscribe_from_agent(self, websocket: WebSocket, agent_name: str):
        """Unsubscribe a connection from agent-specific updates."""
        if agent_name in self.agent_subscriptions:
            if websocket in self.agent_subscriptions[agent_name]:
                self.agent_subscriptions[agent_name].remove(websocket)
    
    async def _do_broadcast(self, message: dict):
        """Internal broadcast implementation."""
        disconnected = []
        
        # Broadcast to all connections
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def queue_broadcast(self, message: dict):
        """Queue a message for broadcast."""
        await self.message_queue.put(message)
    
    async def broadcast_agent_status(
        self,
        agent_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Broadcast agent status update to all connected clients."""
        message = {
            "type": "agent_status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": agent_name,
            "status": status,
            "details": details or {},
        }
        await self.queue_broadcast(message)
        
        # Also send to agent-specific subscribers
        if agent_name in self.agent_subscriptions:
            disconnected = []
            for connection in self.agent_subscriptions[agent_name]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn)
    
    async def broadcast_fleet_status(self, fleet_status: FleetStatus):
        """Broadcast fleet-wide status update."""
        await self.queue_broadcast({
            "type": "fleet_status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fleet": fleet_status.dict(),
        })
    
    async def broadcast_market_event(self, event_type: str, payload: Dict[str, Any]):
        """Broadcast market event to all connected clients."""
        await self.queue_broadcast({
            "type": "market_event",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        })
    
    async def broadcast_signal(self, signal: Dict[str, Any]):
        """Broadcast trading signal to all connected clients."""
        await self.queue_broadcast({
            "type": "signal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal": signal,
        })
    
    async def broadcast_agent_message(self, message: AgentMessage):
        """Broadcast agent-to-agent message."""
        await self.queue_broadcast({
            "type": "agent_message",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message.dict(),
        })


# Global WebSocket manager instance
fleet_ws_manager = AgentFleetWebSocketManager()


# ============================================================================
# Fleet Management Endpoints
# ============================================================================

@router.get("/status", response_model=FleetStatus)
def get_fleet_status(db: Session = Depends(get_db)):
    """
    Get current fleet-wide status summary.
    
    Returns aggregate statistics about all agents in the fleet.
    """
    # Get agent instance counts by status
    status_counts = {}
    for status in AgentStatus:
        count = db.scalar(
            select(AgentInstance).where(AgentInstance.status == status.value).count()
        ) or 0
        status_counts[status.value] = count
    
    total = sum(status_counts.values())
    
    # Calculate health score
    if total > 0:
        healthy_count = status_counts.get("running", 0) + status_counts.get("idle", 0)
        health_score = healthy_count / total
    else:
        health_score = 0.0
    
    return FleetStatus(
        total_agents=total,
        running=status_counts.get("running", 0),
        idle=status_counts.get("idle", 0),
        paused=status_counts.get("paused", 0),
        error=status_counts.get("error", 0),
        stopped=status_counts.get("stopped", 0),
        health_score=round(health_score, 4),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/bulk-operation", response_model=BatchOperationResult)
async def bulk_agent_operation(
    operation: AgentBulkOperation,
    db: Session = Depends(get_db),
):
    """
    Execute a bulk operation on multiple agents.
    
    Supported commands: start, stop, pause, resume, restart, configure
    """
    operation_id = f"bulk_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{id(operation)}"
    started_at = datetime.now(timezone.utc).isoformat()
    
    results = []
    succeeded = 0
    failed = 0
    
    for agent_name in operation.agent_names:
        try:
            # Get or create agent instance
            instance = db.scalar(
                select(AgentInstance).where(AgentInstance.agent_name == agent_name)
            )
            
            if operation.command == AgentCommand.START:
                if not instance:
                    instance = AgentInstance(
                        agent_name=agent_name,
                        instance_id=f"{agent_name}_{int(datetime.now(timezone.utc).timestamp())}",
                        status="running",
                    )
                    db.add(instance)
                else:
                    instance.status = "running"
                    instance.updated_at = datetime.now(timezone.utc)
                
                # Log the start
                db.add(AgentLog(
                    instance_id=instance.instance_id,
                    level="info",
                    message=f"Agent started via bulk operation",
                    context={"operation_id": operation_id, "reason": operation.reason},
                ))
                
            elif operation.command == AgentCommand.STOP:
                if instance:
                    instance.status = "stopped"
                    instance.updated_at = datetime.now(timezone.utc)
                    db.add(AgentLog(
                        instance_id=instance.instance_id,
                        level="info",
                        message=f"Agent stopped via bulk operation",
                        context={"operation_id": operation_id, "reason": operation.reason},
                    ))
                
            elif operation.command == AgentCommand.PAUSE:
                if instance:
                    instance.status = "paused"
                    instance.updated_at = datetime.now(timezone.utc)
                    db.add(AgentLog(
                        instance_id=instance.instance_id,
                        level="info",
                        message=f"Agent paused via bulk operation",
                        context={"operation_id": operation_id},
                    ))
                
            elif operation.command == AgentCommand.RESUME:
                if instance:
                    instance.status = "running"
                    instance.updated_at = datetime.now(timezone.utc)
                    db.add(AgentLog(
                        instance_id=instance.instance_id,
                        level="info",
                        message=f"Agent resumed via bulk operation",
                        context={"operation_id": operation_id},
                    ))
                
            elif operation.command == AgentCommand.RESTART:
                if instance:
                    instance.status = "running"
                    instance.error_count = 0
                    instance.updated_at = datetime.now(timezone.utc)
                    db.add(AgentLog(
                        instance_id=instance.instance_id,
                        level="info",
                        message=f"Agent restarted via bulk operation",
                        context={"operation_id": operation_id, "reason": operation.reason},
                    ))
                
            elif operation.command == AgentCommand.CONFIGURE:
                if instance and operation.config:
                    # Store config in instance metadata
                    instance.last_output = json.dumps(operation.config.dict())
                    instance.updated_at = datetime.now(timezone.utc)
                    db.add(AgentLog(
                        instance_id=instance.instance_id,
                        level="info",
                        message=f"Agent configured via bulk operation",
                        context={
                            "operation_id": operation_id,
                            "config": operation.config.dict(),
                        },
                    ))
            
            db.commit()
            
            # Broadcast status update
            if instance:
                await fleet_ws_manager.broadcast_agent_status(
                    agent_name=agent_name,
                    status=instance.status,
                    details={"operation": operation.command.value},
                )
            
            results.append({
                "agent_name": agent_name,
                "success": True,
                "status": instance.status if instance else "unknown",
            })
            succeeded += 1
            
        except Exception as e:
            results.append({
                "agent_name": agent_name,
                "success": False,
                "error": str(e),
            })
            failed += 1
    
    # Log the bulk operation
    log_event(db, "BULK_AGENT_OPERATION", {
        "operation_id": operation_id,
        "command": operation.command.value,
        "total": len(operation.agent_names),
        "succeeded": succeeded,
        "failed": failed,
    })
    
    return BatchOperationResult(
        operation_id=operation_id,
        command=operation.command.value,
        total=len(operation.agent_names),
        succeeded=succeeded,
        failed=failed,
        results=results,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================================
# Agent Communication Endpoints
# ============================================================================

@router.post("/message")
async def send_agent_message(
    message: AgentMessage,
    db: Session = Depends(get_db),
):
    """
    Send a message from one agent to another.
    
    Messages are broadcast via WebSocket and stored for delivery.
    """
    # Verify sender and recipient exist
    sender = db.scalar(
        select(AgentInstance).where(AgentInstance.agent_name == message.from_agent)
    )
    recipient = db.scalar(
        select(AgentInstance).where(AgentInstance.agent_name == message.to_agent)
    )
    
    if not sender:
        raise HTTPException(status_code=404, detail=f"Sender agent '{message.from_agent}' not found")
    
    # Store the message
    message_record = {
        "id": f"msg_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "from_agent": message.from_agent,
        "to_agent": message.to_agent,
        "message_type": message.message_type,
        "payload": message.payload,
        "priority": message.priority,
        "ttl_seconds": message.ttl_seconds,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "delivered": False,
    }
    
    # Log the message
    db.add(AgentLog(
        instance_id=sender.instance_id,
        level="info",
        message=f"Message sent to {message.to_agent}: {message.message_type}",
        context={
            "message_id": message_record["id"],
            "to_agent": message.to_agent,
            "message_type": message.message_type,
        },
    ))
    
    if recipient:
        db.add(AgentLog(
            instance_id=recipient.instance_id,
            level="info",
            message=f"Message received from {message.from_agent}: {message.message_type}",
            context={
                "message_id": message_record["id"],
                "from_agent": message.from_agent,
                "message_type": message.message_type,
            },
        ))
    
    db.commit()
    
    # Broadcast the message
    await fleet_ws_manager.broadcast_agent_message(message)
    
    return {
        "message_id": message_record["id"],
        "status": "delivered" if recipient else "queued",
        "timestamp": message_record["created_at"],
    }


@router.post("/broadcast")
async def broadcast_to_agents(
    broadcast: AgentBroadcast,
    db: Session = Depends(get_db),
):
    """
    Broadcast a message to multiple agents.
    
    Can target agents by tags or broadcast to all (except excluded agents).
    """
    # Build target agent list
    query = select(AgentInstance)
    
    if broadcast.target_tags:
        # Filter by tags (stored in instance metadata)
        # This is a simplified implementation
        pass
    
    if broadcast.exclude_agents:
        query = query.where(AgentInstance.agent_name.notin_(broadcast.exclude_agents))
    
    targets = db.scalars(query).all()
    
    # Broadcast the message
    await fleet_ws_manager.queue_broadcast({
        "type": "broadcast",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sender": broadcast.sender,
        "message_type": broadcast.message_type,
        "payload": broadcast.payload,
        "target_count": len(targets),
    })
    
    return {
        "broadcast_id": f"bc_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "sender": broadcast.sender,
        "target_count": len(targets),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/messages/{agent_name}")
def get_agent_messages(
    agent_name: str,
    direction: str = Query("inbound", description="Message direction: inbound, outbound, or all"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Get messages for a specific agent.
    
    Returns inbound, outbound, or all messages.
    """
    # Get agent instance
    instance = db.scalar(
        select(AgentInstance).where(AgentInstance.agent_name == agent_name)
    )
    
    if not instance:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    # Query logs for message-related entries
    query = select(AgentLog).where(AgentLog.instance_id == instance.instance_id)
    
    if direction == "inbound":
        query = query.where(AgentLog.message.like("%received%"))
    elif direction == "outbound":
        query = query.where(AgentLog.message.like("%sent%"))
    
    query = query.order_by(desc(AgentLog.created_at)).limit(limit)
    logs = db.scalars(query).all()
    
    messages = []
    for log in logs:
        messages.append({
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "level": log.level,
            "message": log.message,
            "context": log.context,
        })
    
    return {
        "agent_name": agent_name,
        "direction": direction,
        "messages": messages,
        "count": len(messages),
    }


# ============================================================================
# Agent Group Management
# ============================================================================

@router.get("/groups")
def list_agent_groups(
    db: Session = Depends(get_db),
):
    """List all agent groups."""
    # For now, return groups based on agent naming patterns
    agents = db.scalars(select(AgentInstance)).all()
    
    # Group by prefix (e.g., "market_structure", "risk_manager" -> "market", "risk")
    groups = {}
    for agent in agents:
        prefix = agent.agent_name.split("_")[0] if "_" in agent.agent_name else "other"
        if prefix not in groups:
            groups[prefix] = {
                "name": prefix,
                "description": f"Agents with '{prefix}' prefix",
                "agent_names": [],
                "config": {},
            }
        groups[prefix]["agent_names"].append(agent.agent_name)
    
    return {
        "groups": list(groups.values()),
        "count": len(groups),
    }


@router.post("/groups/{group_name}/operation")
async def operate_on_group(
    group_name: str,
    operation: AgentBulkOperation,
    db: Session = Depends(get_db),
):
    """
    Execute a bulk operation on all agents in a group.
    """
    # Get agents in the group
    agents = db.scalars(
        select(AgentInstance).where(AgentInstance.agent_name.like(f"{group_name}_%"))
    ).all()
    
    if not agents:
        raise HTTPException(status_code=404, detail=f"No agents found in group '{group_name}'")
    
    # Update operation with group agents
    operation.agent_names = [a.agent_name for a in agents]
    
    # Execute the bulk operation
    return await bulk_agent_operation(operation, db)


# ============================================================================
# Agent Configuration Management
# ============================================================================

@router.get("/config/{agent_name}")
def get_agent_config(
    agent_name: str,
    db: Session = Depends(get_db),
):
    """Get current configuration for an agent."""
    instance = db.scalar(
        select(AgentInstance).where(AgentInstance.agent_name == agent_name)
    )
    
    if not instance:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    # Parse stored config
    config = {}
    if instance.last_output:
        try:
            config = json.loads(instance.last_output)
        except json.JSONDecodeError:
            pass
    
    return {
        "agent_name": agent_name,
        "instance_id": instance.instance_id,
        "status": instance.status,
        "config": config,
        "health_score": instance.health_score,
        "error_count": instance.error_count,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }


@router.put("/config/{agent_name}")
async def update_agent_config(
    agent_name: str,
    config: AgentConfig,
    db: Session = Depends(get_db),
):
    """Update configuration for an agent."""
    instance = db.scalar(
        select(AgentInstance).where(AgentInstance.agent_name == agent_name)
    )
    
    if not instance:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    # Store config
    instance.last_output = json.dumps(config.dict())
    instance.updated_at = datetime.now(timezone.utc)
    
    # Log the config change
    db.add(AgentLog(
        instance_id=instance.instance_id,
        level="info",
        message="Agent configuration updated",
        context={"config": config.dict()},
    ))
    
    db.commit()
    
    # Broadcast config update
    await fleet_ws_manager.broadcast_agent_status(
        agent_name=agent_name,
        status=instance.status,
        details={"event": "config_updated", "config": config.dict()},
    )
    
    return {
        "agent_name": agent_name,
        "config": config.dict(),
        "updated_at": instance.updated_at.isoformat(),
    }


@router.post("/config/apply-template")
async def apply_config_template(
    template_name: str = Body(...),
    target_agents: List[str] = Body(default_factory=list),
    db: Session = Depends(get_db),
):
    """
    Apply a configuration template to multiple agents.
    
    Templates: 'conservative', 'aggressive', 'balanced', 'research', 'production'
    """
    templates = {
        "conservative": {
            "priority": 3,
            "max_retries": 5,
            "timeout_seconds": 600,
            "parameters": {"risk_threshold": 0.8, "confirmation_required": True},
        },
        "aggressive": {
            "priority": 8,
            "max_retries": 2,
            "timeout_seconds": 180,
            "parameters": {"risk_threshold": 0.4, "confirmation_required": False},
        },
        "balanced": {
            "priority": 5,
            "max_retries": 3,
            "timeout_seconds": 300,
            "parameters": {"risk_threshold": 0.6, "confirmation_required": True},
        },
        "research": {
            "priority": 2,
            "max_retries": 1,
            "timeout_seconds": 900,
            "parameters": {"verbose_logging": True, "save_outputs": True},
        },
        "production": {
            "priority": 7,
            "max_retries": 3,
            "timeout_seconds": 240,
            "parameters": {"verbose_logging": False, "save_outputs": False, "alert_on_error": True},
        },
    }
    
    if template_name not in templates:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template '{template_name}'. Available: {list(templates.keys())}"
        )
    
    template = templates[template_name]
    
    # Apply to target agents
    results = []
    for agent_name in target_agents:
        instance = db.scalar(
            select(AgentInstance).where(AgentInstance.agent_name == agent_name)
        )
        
        if instance:
            instance.last_output = json.dumps(template)
            instance.updated_at = datetime.now(timezone.utc)
            
            db.add(AgentLog(
                instance_id=instance.instance_id,
                level="info",
                message=f"Applied template: {template_name}",
                context={"template": template_name, "config": template},
            ))
            
            results.append({"agent_name": agent_name, "applied": True})
        else:
            results.append({"agent_name": agent_name, "applied": False, "error": "Agent not found"})
    
    db.commit()
    
    return {
        "template": template_name,
        "applied_count": sum(1 for r in results if r.get("applied")),
        "results": results,
    }


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws")
async def agent_fleet_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent fleet updates.
    
    Supports:
    - Agent status updates
    - Fleet-wide status broadcasts
    - Market event streaming
    - Signal distribution
    - Agent-to-agent message relay
    
    Client commands:
    - subscribe: Subscribe to specific agent updates
    - unsubscribe: Unsubscribe from agent updates
    - ping: Connection health check
    - get_fleet_status: Request current fleet status
    """
    await fleet_ws_manager.connect(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Connected to agent fleet WebSocket",
            "capabilities": [
                "agent_status_updates",
                "fleet_status_updates",
                "market_events",
                "signal_distribution",
                "agent_messaging",
            ],
        })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_json()
                action = data.get("action")
                
                if action == "subscribe":
                    agent_name = data.get("agent_name")
                    if agent_name:
                        fleet_ws_manager.subscribe_to_agent(websocket, agent_name)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "agent_name": agent_name,
                        "message": f"Subscribed to updates for {agent_name}" if agent_name else "Subscribed to all fleet updates",
                    })
                
                elif action == "unsubscribe":
                    agent_name = data.get("agent_name")
                    if agent_name:
                        fleet_ws_manager.unsubscribe_from_agent(websocket, agent_name)
                    await websocket.send_json({
                        "type": "unsubscription_confirmed",
                        "agent_name": agent_name,
                    })
                
                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                
                elif action == "get_fleet_status":
                    # This would require db access - simplified response
                    await websocket.send_json({
                        "type": "fleet_status_response",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": "Use GET /agent-fleet/status for full status",
                    })
                
                elif action == "broadcast":
                    # Client requesting to broadcast a message
                    message = data.get("message", {})
                    await fleet_ws_manager.queue_broadcast({
                        "type": "client_broadcast",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "payload": message,
                    })
                
            except Exception as e:
                # Handle receive errors
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
                
    except WebSocketDisconnect:
        pass
    finally:
        fleet_ws_manager.disconnect(websocket)


# ============================================================================
# Market Event Broadcasting
# ============================================================================

@router.post("/broadcast/market-event")
async def broadcast_market_event(
    event_type: str = Body(...),
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
):
    """
    Broadcast a market event to all connected clients.
    
    Event types: price_alert, volume_spike, news, earnings, market_open, market_close
    """
    valid_event_types = ["price_alert", "volume_spike", "news", "earnings", "market_open", "market_close", "signal"]
    
    if event_type not in valid_event_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type. Valid types: {valid_event_types}"
        )
    
    await fleet_ws_manager.broadcast_market_event(event_type, payload)
    
    return {
        "event_type": event_type,
        "broadcasted": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/broadcast/signal")
async def broadcast_trading_signal(
    signal: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """
    Broadcast a trading signal to all connected clients.
    """
    # Validate signal structure
    required_fields = ["ticker", "action", "confidence"]
    missing = [f for f in required_fields if f not in signal]
    
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {missing}"
        )
    
    await fleet_ws_manager.broadcast_signal(signal)
    
    return {
        "signal_broadcasted": True,
        "ticker": signal.get("ticker"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Helper Functions for External Use
# ============================================================================

async def broadcast_agent_update(agent_name: str, status: str, details: Optional[Dict[str, Any]] = None):
    """
    Broadcast an agent status update to all connected WebSocket clients.
    
    This function can be imported and used by other services to notify
    clients of agent activity in real-time.
    """
    await fleet_ws_manager.broadcast_agent_status(
        agent_name=agent_name,
        status=status,
        details=details or {},
    )


async def broadcast_fleet_update(fleet_status: FleetStatus):
    """Broadcast fleet status update."""
    await fleet_ws_manager.broadcast_fleet_status(fleet_status)


async def broadcast_market_event_helper(event_type: str, payload: Dict[str, Any]):
    """Helper to broadcast market events from other modules."""
    await fleet_ws_manager.broadcast_market_event(event_type, payload)
