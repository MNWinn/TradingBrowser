import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import AuditLog, ComplianceViolation
from app.schemas.compliance import ViolationBulkUpdateRequest, ViolationCreateRequest, ViolationUpdateRequest
from app.services.audit import log_event
from app.services.compliance import record_violation

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _serialize_violation(r: ComplianceViolation) -> dict:
    age_seconds = max(0, int((datetime.utcnow() - r.created_at).total_seconds())) if r.created_at else 0
    return {
        "id": r.id,
        "policy_name": r.policy_name,
        "rule_code": r.rule_code,
        "severity": r.severity,
        "status": r.status,
        "symbol": r.symbol,
        "details": r.details,
        "acknowledged_by": r.acknowledged_by,
        "assignee": r.assignee,
        "resolution_notes": r.resolution_notes,
        "resolved_at": r.resolved_at,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
        "age_seconds": age_seconds,
    }


@router.get("/violations")
def list_violations(
    status: str | None = None,
    severity: str | None = None,
    symbol: str | None = None,
    policy_name: str | None = None,
    assignee: str | None = None,
    limit: int = 100,
    sort: str = "newest",
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    safe_limit = min(max(limit, 1), 500)
    stmt = select(ComplianceViolation)

    if status:
        stmt = stmt.where(ComplianceViolation.status == status)
    if severity:
        stmt = stmt.where(ComplianceViolation.severity == severity)
    if symbol:
        stmt = stmt.where(ComplianceViolation.symbol == symbol.upper())
    if policy_name:
        stmt = stmt.where(ComplianceViolation.policy_name == policy_name)
    if assignee:
        stmt = stmt.where(ComplianceViolation.assignee == assignee)

    if sort == "oldest":
        stmt = stmt.order_by(ComplianceViolation.id.asc())
    elif sort == "severity":
        severity_order = case(
            (ComplianceViolation.severity == "critical", 4),
            (ComplianceViolation.severity == "high", 3),
            (ComplianceViolation.severity == "medium", 2),
            else_=1,
        )
        stmt = stmt.order_by(severity_order.desc(), ComplianceViolation.id.desc())
    else:
        stmt = stmt.order_by(ComplianceViolation.id.desc())

    stmt = stmt.limit(safe_limit)
    rows = db.scalars(stmt).all()
    return {"items": [_serialize_violation(r) for r in rows]}


@router.get("/summary")
def violation_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    rows = db.execute(
        select(ComplianceViolation.status, func.count(ComplianceViolation.id)).group_by(ComplianceViolation.status)
    ).all()
    counts = {status: count for status, count in rows}
    return {
        "open": counts.get("open", 0),
        "acknowledged": counts.get("acknowledged", 0),
        "waived": counts.get("waived", 0),
        "remediated": counts.get("remediated", 0),
    }


@router.get("/analytics")
def violation_analytics(
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    rows = db.scalars(select(ComplianceViolation)).all()
    now = datetime.utcnow()

    open_rows = [r for r in rows if r.status in {"open", "acknowledged"}]
    resolved_rows = [r for r in rows if r.status in {"waived", "remediated"} and r.resolved_at and r.created_at]

    mttr_hours = 0.0
    if resolved_rows:
        total_seconds = sum((r.resolved_at - r.created_at).total_seconds() for r in resolved_rows)
        mttr_hours = round((total_seconds / len(resolved_rows)) / 3600, 2)

    def _sla_seconds(severity: str) -> int:
        if severity == "critical":
            return 15 * 60
        if severity == "high":
            return 60 * 60
        if severity == "medium":
            return 4 * 60 * 60
        return 24 * 60 * 60

    overdue = 0
    severe_open = 0
    for r in open_rows:
        if r.severity in {"critical", "high"}:
            severe_open += 1
        if r.created_at and (now - r.created_at).total_seconds() > _sla_seconds(r.severity):
            overdue += 1

    by_severity_rows = db.execute(
        select(ComplianceViolation.severity, func.count(ComplianceViolation.id)).group_by(ComplianceViolation.severity)
    ).all()
    by_severity = {sev: count for sev, count in by_severity_rows}

    return {
        "open_total": len(open_rows),
        "resolved_total": len(resolved_rows),
        "mttr_hours": mttr_hours,
        "sla_overdue_open": overdue,
        "severe_open": severe_open,
        "by_severity": {
            "critical": by_severity.get("critical", 0),
            "high": by_severity.get("high", 0),
            "medium": by_severity.get("medium", 0),
            "low": by_severity.get("low", 0),
        },
    }


@router.post("/violations")
def create_violation(
    payload: ViolationCreateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_roles("admin", "trader")),
):
    row = record_violation(
        db,
        policy_name=payload.policy_name,
        rule_code=payload.rule_code,
        severity=payload.severity,
        symbol=payload.symbol,
        assignee=payload.assignee,
        details=payload.details,
    )
    log_event(
        db,
        "COMPLIANCE_VIOLATION_CREATED",
        {"id": row.id, "rule_code": row.rule_code, "status": row.status, "assignee": row.assignee},
        actor=actor,
    )
    return {"id": row.id, "status": row.status}


@router.patch("/violations/{violation_id}")
def update_violation(
    violation_id: int,
    payload: ViolationUpdateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_roles("admin", "trader")),
):
    row = db.scalar(select(ComplianceViolation).where(ComplianceViolation.id == violation_id))
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found")

    row.status = payload.status
    row.acknowledged_by = payload.acknowledged_by or actor
    if payload.assignee is not None:
        row.assignee = payload.assignee
    row.resolution_notes = payload.resolution_notes
    row.updated_at = datetime.utcnow()
    if payload.status in {"waived", "remediated"}:
        row.resolved_at = datetime.utcnow()

    db.add(row)
    db.commit()
    db.refresh(row)

    log_event(
        db,
        "COMPLIANCE_VIOLATION_UPDATED",
        {
            "id": row.id,
            "status": row.status,
            "acknowledged_by": row.acknowledged_by,
            "assignee": row.assignee,
            "resolution_notes": row.resolution_notes,
        },
        actor=actor,
    )
    return {"id": row.id, "status": row.status, "updated_at": row.updated_at, "age_seconds": _serialize_violation(row)["age_seconds"]}


@router.patch("/violations-bulk")
def bulk_update_violations(
    payload: ViolationBulkUpdateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_roles("admin", "trader")),
):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids is required")

    rows = db.scalars(select(ComplianceViolation).where(ComplianceViolation.id.in_(payload.ids))).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No matching violations")

    now = datetime.utcnow()
    for row in rows:
        row.status = payload.status
        row.acknowledged_by = payload.acknowledged_by or actor
        if payload.assignee is not None:
            row.assignee = payload.assignee
        row.resolution_notes = payload.resolution_notes
        row.updated_at = now
        if payload.status in {"waived", "remediated"}:
            row.resolved_at = now

    db.commit()

    log_event(
        db,
        "COMPLIANCE_VIOLATION_BULK_UPDATED",
        {
            "ids": payload.ids,
            "status": payload.status,
            "assignee": payload.assignee,
            "count": len(rows),
        },
        actor=actor,
    )

    return {"updated": len(rows), "status": payload.status}


@router.get("/violations/{violation_id}/timeline")
def violation_timeline(
    violation_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    row = db.scalar(select(ComplianceViolation).where(ComplianceViolation.id == violation_id))
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found")

    safe_limit = min(max(limit, 1), 500)
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.event_type.in_([
            "COMPLIANCE_VIOLATION_CREATED",
            "COMPLIANCE_VIOLATION_UPDATED",
            "COMPLIANCE_VIOLATION_BULK_UPDATED",
        ]))
        .order_by(AuditLog.id.desc())
        .limit(2000)
    ).all()

    matched = []
    for lg in logs:
        payload = lg.payload or {}
        ids = payload.get("ids") if isinstance(payload, dict) else None
        if payload.get("id") == violation_id or (isinstance(ids, list) and violation_id in ids):
            matched.append(
                {
                    "event_type": lg.event_type,
                    "actor": lg.actor,
                    "payload": payload,
                    "created_at": lg.created_at,
                }
            )

    timeline = [
        {
            "event_type": "COMPLIANCE_VIOLATION_CREATED",
            "actor": row.acknowledged_by,
            "payload": {
                "id": row.id,
                "status": row.status,
                "assignee": row.assignee,
                "rule_code": row.rule_code,
            },
            "created_at": row.created_at,
        },
        *reversed(matched),
    ]

    dedup = []
    seen = set()
    for e in timeline:
        key = (e["event_type"], str(e.get("created_at")), str(e.get("payload")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)

    return {"violation_id": violation_id, "items": dedup[-safe_limit:]}


@router.get("/violations/export.csv")
def export_violations_csv(
    status: str | None = None,
    severity: str | None = None,
    symbol: str | None = None,
    policy_name: str | None = None,
    assignee: str | None = None,
    sort: str = "newest",
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    stmt = select(ComplianceViolation)
    if status:
        stmt = stmt.where(ComplianceViolation.status == status)
    if severity:
        stmt = stmt.where(ComplianceViolation.severity == severity)
    if symbol:
        stmt = stmt.where(ComplianceViolation.symbol == symbol.upper())
    if policy_name:
        stmt = stmt.where(ComplianceViolation.policy_name == policy_name)
    if assignee:
        stmt = stmt.where(ComplianceViolation.assignee == assignee)

    if sort == "oldest":
        stmt = stmt.order_by(ComplianceViolation.id.asc())
    elif sort == "severity":
        severity_order = case(
            (ComplianceViolation.severity == "critical", 4),
            (ComplianceViolation.severity == "high", 3),
            (ComplianceViolation.severity == "medium", 2),
            else_=1,
        )
        stmt = stmt.order_by(severity_order.desc(), ComplianceViolation.id.desc())
    else:
        stmt = stmt.order_by(ComplianceViolation.id.desc())

    rows = db.scalars(stmt).all()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "id",
        "policy_name",
        "rule_code",
        "severity",
        "status",
        "symbol",
        "acknowledged_by",
        "assignee",
        "resolution_notes",
        "resolved_at",
        "created_at",
        "updated_at",
        "age_seconds",
    ])
    for r in rows:
        sr = _serialize_violation(r)
        writer.writerow(
            [
                sr["id"],
                sr["policy_name"],
                sr["rule_code"],
                sr["severity"],
                sr["status"],
                sr["symbol"],
                sr["acknowledged_by"],
                sr["assignee"],
                sr["resolution_notes"],
                sr["resolved_at"],
                sr["created_at"],
                sr["updated_at"],
                sr["age_seconds"],
            ]
        )

    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="compliance_violations.csv"'},
    )
