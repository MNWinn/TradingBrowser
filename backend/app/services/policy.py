from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import ExecutionMode, RiskPolicy


DEFAULT_HARD_CONSTRAINTS = {
    "max_capital_per_trade": 2000,
    "max_risk_pct_per_trade": 0.01,
    "max_daily_loss": 500,
    "max_weekly_loss": 1500,
    "max_concurrent_positions": 5,
    "kill_switch": False,
}

DEFAULT_SOFT_CONSTRAINTS = {
    "size_multiplier": 1.0,
    "confidence_multiplier": 1.0,
    "soft_size_cap": 2000,
}


def validate_mode_transition(mode: str, live_enabled: bool, confirmation: str | None) -> None:
    if mode not in {"research", "paper", "live"}:
        raise ValueError("Invalid mode")
    if mode == "live":
        if not live_enabled:
            raise ValueError("Live mode requires live_trading_enabled=true")
        if confirmation != "ENABLE_LIVE_TRADING":
            raise ValueError("Live mode requires explicit confirmation token")


def get_runtime_mode(db: Session) -> tuple[str, bool]:
    latest = db.scalar(select(ExecutionMode).order_by(ExecutionMode.id.desc()).limit(1))
    if not latest:
        return settings.mode, settings.live_trading_enabled
    return latest.mode, latest.live_enabled


def set_runtime_mode(db: Session, mode: str, live_enabled: bool, changed_by: str = "system") -> ExecutionMode:
    row = ExecutionMode(mode=mode, live_enabled=live_enabled, changed_by=changed_by, changed_at=datetime.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_risk_policy(db: Session, profile_name: str = "default") -> RiskPolicy:
    row = db.scalar(select(RiskPolicy).where(RiskPolicy.profile_name == profile_name))
    if row:
        return row
    row = RiskPolicy(
        profile_name=profile_name,
        hard_constraints=DEFAULT_HARD_CONSTRAINTS,
        soft_constraints=DEFAULT_SOFT_CONSTRAINTS,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
