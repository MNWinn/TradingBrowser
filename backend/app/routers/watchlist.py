from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import WatchlistItem
from app.services.audit import log_event

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/{user_id}")
def get_watchlist(user_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(WatchlistItem).where(WatchlistItem.user_id == user_id).order_by(WatchlistItem.position.asc(), WatchlistItem.id.asc())
    ).all()
    return {"items": [r.ticker for r in rows]}


@router.post("/{user_id}/{ticker}")
def add_ticker(user_id: str, ticker: str, db: Session = Depends(get_db)):
    symbol = ticker.upper()
    existing = db.scalar(
        select(WatchlistItem).where(WatchlistItem.user_id == user_id, WatchlistItem.ticker == symbol)
    )
    if not existing:
        last_position = db.scalar(
            select(WatchlistItem.position)
            .where(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.position.desc())
            .limit(1)
        )
        db.add(WatchlistItem(user_id=user_id, ticker=symbol, position=(last_position or 0) + 1))
        db.commit()
        log_event(db, "WATCHLIST_ADD", {"user_id": user_id, "ticker": symbol}, actor=user_id)
    rows = db.scalars(
        select(WatchlistItem).where(WatchlistItem.user_id == user_id).order_by(WatchlistItem.position.asc(), WatchlistItem.id.asc())
    ).all()
    return {"items": [r.ticker for r in rows]}


@router.delete("/{user_id}/{ticker}")
def remove_ticker(user_id: str, ticker: str, db: Session = Depends(get_db)):
    symbol = ticker.upper()
    db.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id, WatchlistItem.ticker == symbol))
    db.commit()
    log_event(db, "WATCHLIST_REMOVE", {"user_id": user_id, "ticker": symbol}, actor=user_id)
    rows = db.scalars(
        select(WatchlistItem).where(WatchlistItem.user_id == user_id).order_by(WatchlistItem.position.asc(), WatchlistItem.id.asc())
    ).all()
    return {"items": [r.ticker for r in rows]}
