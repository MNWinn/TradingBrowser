from collections import defaultdict
from datetime import datetime, date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    SwarmAgentRun,
    SwarmConsensusOutput,
    AgentPerformanceStat,
    DailyModelEvaluation,
    SignalOutput,
)


def run_daily_recalibration(db: Session, eval_date: date | None = None) -> dict:
    target_date = eval_date or datetime.utcnow().date()

    consensus_by_task: dict[str, str] = {
        c.task_id: c.aggregated_recommendation or ""
        for c in db.scalars(select(SwarmConsensusOutput)).all()
    }

    stats = defaultdict(lambda: {"total": 0, "agree": 0, "avg_conf": 0.0})
    for run in db.scalars(select(SwarmAgentRun)).all():
        if run.agent_name in {"risk", "execution", "learning"}:
            continue
        s = stats[run.agent_name]
        s["total"] += 1
        s["avg_conf"] += float(run.confidence or 0.0)
        consensus = consensus_by_task.get(run.task_id)
        if consensus and run.recommendation == consensus:
            s["agree"] += 1

    agent_metrics = {}
    for agent_name, values in stats.items():
        total = max(values["total"], 1)
        reliability = values["agree"] / total
        avg_conf = values["avg_conf"] / total
        agent_metrics[agent_name] = {
            "samples": values["total"],
            "agreement_rate": round(reliability, 4),
            "avg_confidence": round(avg_conf, 4),
        }

        row = db.scalar(
            select(AgentPerformanceStat).where(
                AgentPerformanceStat.agent_name == agent_name,
                AgentPerformanceStat.setup_type.is_(None),
                AgentPerformanceStat.regime.is_(None),
            )
        )
        if not row:
            row = AgentPerformanceStat(agent_name=agent_name, setup_type=None, regime=None)
        row.reliability_score = round(reliability, 4)
        row.stats = agent_metrics[agent_name]
        row.updated_at = datetime.utcnow()
        db.add(row)

    all_signals = db.scalars(select(SignalOutput)).all()
    signal_count = len(all_signals)
    avg_signal_conf = round(sum(float(s.confidence or 0.0) for s in all_signals) / max(signal_count, 1), 4)

    metrics = {
        "date": str(target_date),
        "signal_count": signal_count,
        "avg_signal_confidence": avg_signal_conf,
        "agents": agent_metrics,
    }

    db.add(
        DailyModelEvaluation(
            eval_date=target_date,
            metrics=metrics,
            notes="Auto-recalibrated agent reliability scores from swarm agreement.",
        )
    )
    db.commit()
    return metrics
