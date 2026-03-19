"""Seed default execution mode, risk policy, and demo watchlist.

Run:
  python -m scripts.seed_defaults
from backend/ directory with env configured.
"""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import ExecutionMode, RiskPolicy, WatchlistItem
from app.services.policy import DEFAULT_HARD_CONSTRAINTS, DEFAULT_SOFT_CONSTRAINTS


def run() -> None:
    db = SessionLocal()
    try:
        mode = db.scalar(select(ExecutionMode).order_by(ExecutionMode.id.desc()).limit(1))
        if not mode:
            db.add(ExecutionMode(mode="research", live_enabled=False, changed_by="seed"))

        rp = db.scalar(select(RiskPolicy).where(RiskPolicy.profile_name == "default"))
        if not rp:
            db.add(
                RiskPolicy(
                    profile_name="default",
                    hard_constraints=DEFAULT_HARD_CONSTRAINTS,
                    soft_constraints=DEFAULT_SOFT_CONSTRAINTS,
                )
            )

        existing = db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == "demo")).all()
        if not existing:
            for i, ticker in enumerate(["AAPL", "MSFT", "NVDA", "SPY"], start=1):
                db.add(WatchlistItem(user_id="demo", ticker=ticker, position=i))

        db.commit()
        print("Seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    run()
