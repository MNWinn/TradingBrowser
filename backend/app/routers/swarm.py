from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import SwarmTask, SwarmAgentRun, SwarmConsensusOutput, AgentPerformanceStat
from app.services.audit import log_event
from app.services.focus_runner import run_focus_cycle
from app.services.focus_runtime import add_focus_ticker, get_focus_config, remove_focus_ticker, set_focus_config
from app.services.policy import get_runtime_mode
from app.services.swarm import SwarmOrchestrator

router = APIRouter(prefix="/swarm", tags=["swarm"])
orchestrator = SwarmOrchestrator()


@router.post("/run/{ticker}")
async def run_swarm(ticker: str, db: Session = Depends(get_db)):
    symbol = ticker.upper()
    mode, _ = get_runtime_mode(db)
    started = datetime.now(timezone.utc)
    result = await orchestrator.run(ticker=symbol, mode=mode)
    completed = datetime.now(timezone.utc)

    db.add(
        SwarmTask(
            task_id=result["task_id"],
            ticker=symbol,
            mode=mode,
            status="completed",
            started_at=started,
            completed_at=completed,
        )
    )
    for run in result["agent_runs"]:
        db.add(
            SwarmAgentRun(
                task_id=result["task_id"],
                agent_name=run.get("agent"),
                recommendation=run.get("recommendation"),
                confidence=run.get("confidence"),
                latency_ms=None,
                output=run,
            )
        )
    db.add(
        SwarmConsensusOutput(
            task_id=result["task_id"],
            ticker=symbol,
            aggregated_recommendation=result["aggregated_recommendation"],
            consensus_score=result["consensus_score"],
            disagreement_score=result["disagreement_score"],
            explanation=f"Aggregated from {len(result['agent_runs'])} agents",
        )
    )
    db.commit()
    log_event(db, "SWARM_RUN", {"ticker": symbol, "task_id": result["task_id"], "mode": mode})
    return result


@router.get("/status/{task_id}")
def swarm_status(task_id: str, db: Session = Depends(get_db)):
    task = db.scalar(select(SwarmTask).where(SwarmTask.task_id == task_id))
    if not task:
        return {"task_id": task_id, "status": "not_found"}
    return {
        "task_id": task.task_id,
        "status": task.status,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }


@router.get("/results/{ticker}")
def swarm_results(ticker: str, db: Session = Depends(get_db)):
    symbol = ticker.upper()
    latest = db.scalar(
        select(SwarmTask).where(SwarmTask.ticker == symbol).order_by(SwarmTask.id.desc()).limit(1)
    )
    if not latest:
        return {"ticker": symbol, "latest_task": None, "results": []}

    runs = db.scalars(select(SwarmAgentRun).where(SwarmAgentRun.task_id == latest.task_id)).all()
    consensus = db.scalar(
        select(SwarmConsensusOutput).where(SwarmConsensusOutput.task_id == latest.task_id).order_by(SwarmConsensusOutput.id.desc())
    )
    return {
        "ticker": symbol,
        "latest_task": latest.task_id,
        "results": [
            {
                "agent": r.agent_name,
                "recommendation": r.recommendation,
                "confidence": r.confidence,
                "output": r.output,
            }
            for r in runs
        ],
        "consensus": {
            "recommendation": consensus.aggregated_recommendation if consensus else None,
            "consensus_score": consensus.consensus_score if consensus else None,
            "disagreement_score": consensus.disagreement_score if consensus else None,
        },
    }


@router.get("/performance")
def swarm_performance(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentPerformanceStat).order_by(AgentPerformanceStat.reliability_score.desc())).all()
    return {
        "items": [
            {
                "agent_name": r.agent_name,
                "reliability_score": r.reliability_score,
                "stats": r.stats,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    }


@router.get("/focus")
def get_focus_state():
    return get_focus_config()


@router.put("/focus")
def set_focus_state(payload: dict):
    return set_focus_config(
        tickers=payload.get("tickers"),
        enabled=payload.get("enabled"),
        interval_sec=payload.get("interval_sec"),
    )


@router.post("/focus/run-cycle")
async def run_focus_now():
    return await run_focus_cycle()


@router.post("/focus/{ticker}")
def add_focus_state_ticker(ticker: str):
    try:
        return add_focus_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/focus/{ticker}")
def remove_focus_state_ticker(ticker: str):
    return remove_focus_ticker(ticker)
