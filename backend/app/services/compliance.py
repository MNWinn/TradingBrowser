from datetime import datetime

from sqlalchemy.orm import Session

from app.models.entities import ComplianceViolation


def record_violation(
    db: Session,
    *,
    policy_name: str,
    rule_code: str,
    severity: str = "medium",
    symbol: str | None = None,
    assignee: str | None = None,
    details: dict | None = None,
) -> ComplianceViolation:
    row = ComplianceViolation(
        policy_name=policy_name,
        rule_code=rule_code,
        severity=severity,
        status="open",
        symbol=(symbol or "").upper() or None,
        assignee=assignee,
        details=details or {},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
