from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.audit import log_event
from app.services.evaluation import run_daily_recalibration

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/daily")
def daily_evaluation(db: Session = Depends(get_db)):
    metrics = run_daily_recalibration(db)
    log_event(db, "DAILY_EVALUATION", metrics)

    return {
        "status": "ok",
        "today_learnings": [
            "Agent reliability scores recalibrated from swarm consensus agreement.",
            "Signal confidence trend captured for latest evaluation window.",
        ],
        "metrics": metrics,
    }
