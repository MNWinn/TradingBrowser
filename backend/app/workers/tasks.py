from datetime import datetime

from app.core.database import SessionLocal
from app.services.evaluation import run_daily_recalibration
from app.workers.celery_app import celery_app


@celery_app.task
def run_daily_training():
    db = SessionLocal()
    try:
        metrics = run_daily_recalibration(db)
        return {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "notes": "Recalibrated ensemble weights and updated soft risk heuristics.",
            "metrics": metrics,
        }
    finally:
        db.close()
