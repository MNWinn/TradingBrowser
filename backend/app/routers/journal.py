from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import TradeJournal
from app.schemas.journal import JournalOutcomeUpdate
from app.services.audit import log_event
from app.services.journal import merge_state

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("")
def list_journal(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(select(TradeJournal).order_by(TradeJournal.id.desc()).limit(limit)).all()
    return {
        "items": [
            {
                "id": r.id,
                "ticker": r.ticker,
                "mode": r.mode,
                "recommendation": r.recommendation,
                "execution": r.execution,
                "outcome": r.outcome,
                "tags": r.tags,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.patch("/{entry_id}/outcome")
def update_outcome(
    entry_id: int,
    payload: JournalOutcomeUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader")),
):
    row = db.scalar(select(TradeJournal).where(TradeJournal.id == entry_id))
    if not row:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    outcome = payload.model_dump(exclude_none=True)
    row.outcome = outcome
    row.tags = merge_state(row.tags, outcome.get("state", "closed"))
    db.add(row)
    db.commit()
    db.refresh(row)

    log_event(db, "JOURNAL_OUTCOME_UPDATE", {"entry_id": entry_id, "outcome": outcome})
    return {
        "id": row.id,
        "ticker": row.ticker,
        "mode": row.mode,
        "recommendation": row.recommendation,
        "execution": row.execution,
        "outcome": row.outcome,
        "tags": row.tags,
        "created_at": row.created_at,
    }
