from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def log_event(db: Session, event_type: str, payload: dict, actor: str | None = None) -> None:
    db.add(AuditLog(event_type=event_type, payload=payload, actor=actor))
    db.commit()
