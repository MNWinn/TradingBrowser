from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import PaperOrder, TradeJournal
from app.services.journal import build_outcome, merge_state


def apply_fill_update(db: Session, payload: dict) -> dict:
    broker_order_id = payload.get("broker_order_id")
    state = payload.get("state", "filled")

    paper_order = db.scalar(select(PaperOrder).where(PaperOrder.broker_order_id == broker_order_id))
    if paper_order:
        paper_order.status = state
        db.add(paper_order)

    journal_row = db.scalar(
        select(TradeJournal)
        .where(TradeJournal.execution["broker_order_id"].as_string() == broker_order_id)
        .order_by(TradeJournal.id.desc())
        .limit(1)
    )

    if journal_row:
        journal_row.outcome = build_outcome(payload)
        journal_row.tags = merge_state(journal_row.tags, state)
        db.add(journal_row)

    db.commit()
    return {
        "status": "ok",
        "paper_order_updated": bool(paper_order),
        "journal_updated": bool(journal_row),
    }
