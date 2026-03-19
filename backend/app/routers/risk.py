from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import RiskPolicy
from app.services.audit import log_event
from app.services.policy import get_or_create_risk_policy

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/profile")
def get_profile(db: Session = Depends(get_db)):
    policy = get_or_create_risk_policy(db)
    hard = policy.hard_constraints
    return {
        "capital": 100000,
        "risk_usage_today": 0.12,
        "risk_usage_week": 0.28,
        "hard_constraints": hard,
    }


@router.get("/policy")
def get_policy(profile_name: str = "default", db: Session = Depends(get_db)):
    policy = get_or_create_risk_policy(db, profile_name=profile_name)
    return {
        "profile_name": policy.profile_name,
        "hard_constraints": policy.hard_constraints,
        "soft_constraints": policy.soft_constraints,
        "updated_at": policy.updated_at,
    }


@router.put("/policy")
def update_policy(
    payload: dict,
    profile_name: str = "default",
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin")),
):
    policy = get_or_create_risk_policy(db, profile_name=profile_name)
    policy.hard_constraints = payload.get("hard_constraints", policy.hard_constraints)
    policy.soft_constraints = payload.get("soft_constraints", policy.soft_constraints)
    policy.updated_at = datetime.utcnow()
    db.add(policy)
    db.commit()
    db.refresh(policy)
    log_event(db, "RISK_POLICY_UPDATE", {"profile_name": profile_name, "payload": payload})
    return {
        "profile_name": policy.profile_name,
        "hard_constraints": policy.hard_constraints,
        "soft_constraints": policy.soft_constraints,
        "updated_at": policy.updated_at,
    }
