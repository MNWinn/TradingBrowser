"""Agents API Router with WebSocket support for real-time agent status updates."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import (
    SwarmAgentRun,
    SwarmTask,
    AgentPerformanceStat,
    SwarmConsensusOutput,
)
from app.services.audit import log_event

router = APIRouter(prefix="/agents", tags=["agents"])

# WebSocket connection manager for real-time agent status updates
class AgentWebSocketManager:
    """Manages WebSocket connections for agent status updates."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_agent_status_update(self, agent_name: str, status: str, details: dict):
        """Send agent status update to all connected clients."""
        await self.broadcast({
            "type": "agent_status_update",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": agent_name,
            "status": status,
            "details": details,
        })


# Global WebSocket manager instance
ws_manager = AgentWebSocketManager()


@router.get("")
def list_agents(
    status: Optional[str] = Query(None, description="Filter by agent status"),
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db),
):
    """
    List all agents with optional filtering by status and ticker.
    
    Returns a list of agent runs with their latest status and metadata.
    """
    # Build query for agent runs
    query = select(SwarmAgentRun).order_by(desc(SwarmAgentRun.id))
    
    # Apply filters if provided
    if status:
        # Join with SwarmTask to filter by task status
        query = query.join(SwarmTask, SwarmAgentRun.task_id == SwarmTask.task_id)
        query = query.where(SwarmTask.status == status)
    
    if ticker:
        query = query.join(SwarmTask, SwarmAgentRun.task_id == SwarmTask.task_id)
        query = query.where(SwarmTask.ticker == ticker.upper())
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    agent_runs = db.scalars(query).all()
    
    # Get unique agents with their latest runs
    agents_map = {}
    for run in agent_runs:
        if run.agent_name not in agents_map:
            agents_map[run.agent_name] = {
                "agent_name": run.agent_name,
                "latest_task_id": run.task_id,
                "latest_recommendation": run.recommendation,
                "latest_confidence": run.confidence,
                "output_preview": run.output,
            }
    
    # Get performance stats for each agent
    performance_stats = db.scalars(
        select(AgentPerformanceStat).where(
            AgentPerformanceStat.agent_name.in_(list(agents_map.keys()))
        )
    ).all()
    
    stats_map = {s.agent_name: s for s in performance_stats}
    
    # Combine agent data with performance stats
    items = []
    for agent_name, agent_data in agents_map.items():
        stats = stats_map.get(agent_name)
        items.append({
            **agent_data,
            "reliability_score": stats.reliability_score if stats else None,
            "performance_stats": stats.stats if stats else None,
            "updated_at": stats.updated_at.isoformat() if stats else None,
        })
    
    # Get total count for pagination
    count_query = select(SwarmAgentRun)
    if status or ticker:
        count_query = count_query.join(SwarmTask, SwarmAgentRun.task_id == SwarmTask.task_id)
        if status:
            count_query = count_query.where(SwarmTask.status == status)
        if ticker:
            count_query = count_query.where(SwarmTask.ticker == ticker.upper())
    
    total = db.scalar(select(SwarmAgentRun.id).select_from(count_query.subquery()))
    
    return {
        "items": items,
        "total": len(items) if items else 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{agent_id}")
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific agent.
    
    Includes performance statistics, recent runs, and aggregated metrics.
    """
    # Get agent performance stats
    stats = db.scalar(
        select(AgentPerformanceStat).where(AgentPerformanceStat.agent_name == agent_id)
    )
    
    # Get recent agent runs
    recent_runs = db.scalars(
        select(SwarmAgentRun)
        .where(SwarmAgentRun.agent_name == agent_id)
        .order_by(desc(SwarmAgentRun.id))
        .limit(50)
    ).all()
    
    if not stats and not recent_runs:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    # Get associated tasks
    task_ids = [run.task_id for run in recent_runs]
    tasks = {}
    if task_ids:
        task_rows = db.scalars(
            select(SwarmTask).where(SwarmTask.task_id.in_(task_ids))
        ).all()
        tasks = {t.task_id: t for t in task_rows}
    
    # Build run history with task context
    run_history = []
    for run in recent_runs:
        task = tasks.get(run.task_id)
        run_history.append({
            "task_id": run.task_id,
            "ticker": task.ticker if task else None,
            "recommendation": run.recommendation,
            "confidence": run.confidence,
            "latency_ms": run.latency_ms,
            "output": run.output,
            "task_status": task.status if task else None,
            "started_at": task.started_at.isoformat() if task and task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task and task.completed_at else None,
        })
    
    # Calculate aggregated metrics
    recommendations = [r.recommendation for r in recent_runs if r.recommendation]
    recommendation_counts = {}
    for rec in recommendations:
        recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1
    
    avg_confidence = sum(r.confidence for r in recent_runs if r.confidence) / len(recent_runs) if recent_runs else None
    
    return {
        "agent_name": agent_id,
        "reliability_score": stats.reliability_score if stats else None,
        "performance_stats": stats.stats if stats else None,
        "setup_type": stats.setup_type if stats else None,
        "regime": stats.regime if stats else None,
        "updated_at": stats.updated_at.isoformat() if stats else None,
        "metrics": {
            "total_runs": len(recent_runs),
            "average_confidence": round(avg_confidence, 4) if avg_confidence else None,
            "recommendation_distribution": recommendation_counts,
        },
        "recent_runs": run_history,
    }


@router.get("/{agent_id}/logs")
def get_agent_logs(
    agent_id: str,
    limit: int = Query(50, ge=1, le=500, description="Number of log entries to return"),
    offset: int = Query(0, ge=0, description="Number of entries to skip"),
    db: Session = Depends(get_db),
):
    """
    Get agent logs with pagination.
    
    Returns detailed log entries for the specified agent.
    """
    # Verify agent exists
    exists = db.scalar(
        select(SwarmAgentRun.id).where(SwarmAgentRun.agent_name == agent_id).limit(1)
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    # Get paginated agent runs as logs
    query = (
        select(SwarmAgentRun)
        .where(SwarmAgentRun.agent_name == agent_id)
        .order_by(desc(SwarmAgentRun.id))
        .offset(offset)
        .limit(limit)
    )
    
    runs = db.scalars(query).all()
    
    # Get associated tasks for context
    task_ids = [run.task_id for run in runs]
    tasks = {}
    if task_ids:
        task_rows = db.scalars(
            select(SwarmTask).where(SwarmTask.task_id.in_(task_ids))
        ).all()
        tasks = {t.task_id: t for t in task_rows}
    
    # Build log entries
    logs = []
    for run in runs:
        task = tasks.get(run.task_id)
        logs.append({
            "log_id": run.id,
            "task_id": run.task_id,
            "ticker": task.ticker if task else None,
            "timestamp": task.completed_at.isoformat() if task and task.completed_at else None,
            "recommendation": run.recommendation,
            "confidence": run.confidence,
            "latency_ms": run.latency_ms,
            "output": run.output,
        })
    
    # Get total count
    total = db.scalar(
        select(SwarmAgentRun.id)
        .where(SwarmAgentRun.agent_name == agent_id)
        .select_from(SwarmAgentRun)
    ) or 0
    
    return {
        "agent_name": agent_id,
        "logs": logs,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        },
    }


@router.get("/{agent_id}/outputs")
def get_agent_outputs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100, description="Number of outputs to return"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    db: Session = Depends(get_db),
):
    """
    Get recent agent outputs.
    
    Returns the most recent outputs from the agent, optionally filtered by ticker.
    """
    # Verify agent exists
    exists = db.scalar(
        select(SwarmAgentRun.id).where(SwarmAgentRun.agent_name == agent_id).limit(1)
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    
    # Build query
    query = select(SwarmAgentRun).where(SwarmAgentRun.agent_name == agent_id)
    
    # Filter by ticker if provided (requires join)
    if ticker:
        query = query.join(SwarmTask, SwarmAgentRun.task_id == SwarmTask.task_id)
        query = query.where(SwarmTask.ticker == ticker.upper())
    
    query = query.order_by(desc(SwarmAgentRun.id)).limit(limit)
    
    runs = db.scalars(query).all()
    
    # Get associated tasks and consensus outputs
    task_ids = [run.task_id for run in runs]
    tasks = {}
    consensus_map = {}
    
    if task_ids:
        task_rows = db.scalars(
            select(SwarmTask).where(SwarmTask.task_id.in_(task_ids))
        ).all()
        tasks = {t.task_id: t for t in task_rows}
        
        consensus_rows = db.scalars(
            select(SwarmConsensusOutput).where(SwarmConsensusOutput.task_id.in_(task_ids))
        ).all()
        consensus_map = {c.task_id: c for c in consensus_rows}
    
    # Build output entries
    outputs = []
    for run in runs:
        task = tasks.get(run.task_id)
        consensus = consensus_map.get(run.task_id)
        
        outputs.append({
            "output_id": run.id,
            "task_id": run.task_id,
            "ticker": task.ticker if task else None,
            "timestamp": task.completed_at.isoformat() if task and task.completed_at else None,
            "output": run.output,
            "recommendation": run.recommendation,
            "confidence": run.confidence,
            "consensus": {
                "aggregated_recommendation": consensus.aggregated_recommendation if consensus else None,
                "consensus_score": consensus.consensus_score if consensus else None,
                "disagreement_score": consensus.disagreement_score if consensus else None,
            } if consensus else None,
        })
    
    return {
        "agent_name": agent_id,
        "outputs": outputs,
        "count": len(outputs),
    }


@router.websocket("/ws")
async def agents_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent status updates.
    
    Clients receive updates when:
    - Agent status changes
    - New agent runs are completed
    - Performance metrics are updated
    
    Message format:
    {
        "type": "agent_status_update",
        "timestamp": "2024-01-01T00:00:00Z",
        "agent_name": "market_structure",
        "status": "completed",
        "details": {...}
    }
    """
    await ws_manager.connect(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Connected to agents WebSocket",
        })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for messages from client (with timeout)
                data = await websocket.receive_json()
                
                # Handle client commands
                if data.get("action") == "subscribe":
                    agent_name = data.get("agent_name")
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "agent_name": agent_name,
                        "message": f"Subscribed to updates for {agent_name}" if agent_name else "Subscribed to all agent updates",
                    })
                
                elif data.get("action") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                
                elif data.get("action") == "get_status":
                    # Client requesting current status of all agents
                    # This would typically query the database
                    await websocket.send_json({
                        "type": "status_response",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": "Status query received - implement database query as needed",
                    })
                    
            except Exception as e:
                # Handle receive errors (client disconnect, etc.)
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)


# Helper function to broadcast agent updates (can be called from other modules)
async def broadcast_agent_update(agent_name: str, status: str, details: dict = None):
    """
    Broadcast an agent status update to all connected WebSocket clients.
    
    This function can be imported and used by other services to notify
    clients of agent activity in real-time.
    """
    await ws_manager.send_agent_status_update(
        agent_name=agent_name,
        status=status,
        details=details or {},
    )
