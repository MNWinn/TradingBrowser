from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
def logs(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": r.id,
                "event_type": r.event_type,
                "actor": r.actor,
                "payload": r.payload,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }
