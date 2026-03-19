from fastapi import APIRouter

from app.workers.tasks import run_daily_training

router = APIRouter(prefix="/training", tags=["training"])


@router.post("/run")
def run_training():
    task = run_daily_training.delay()
    return {"task_id": task.id, "status": "queued"}
