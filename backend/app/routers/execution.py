from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.database import get_db
from app.models.entities import (
    AuditLog,
    ComplianceViolation,
    ExecutionMode,
    ExecutionRequest,
    LiveReadinessSnapshot,
    PaperOrder,
    TradeJournal,
)
from app.schemas.execution import (
    LiveReadinessResponse,
    LiveReadinessSnapshotResponse,
    LiveReadinessTrendResponse,
    ModeUpdateRequest,
    OrderFillRequest,
    OrderRequest,
)
from app.services.audit import log_event
from app.services.execution import AdapterFactory
from app.services.orders import apply_fill_update
from app.services.compliance import record_violation
from app.services.mirofish import mirofish_diagnostics
from app.services.policy import (
    get_or_create_risk_policy,
    get_runtime_mode,
    set_runtime_mode,
    validate_mode_transition,
)
from app.services.risk import RiskEngine, RiskState

router = APIRouter(prefix="/execution", tags=["execution"])


def _sla_seconds(severity: str) -> int:
    if severity == "critical":
        return 15 * 60
    if severity == "high":
        return 60 * 60
    if severity == "medium":
        return 4 * 60 * 60
    return 24 * 60 * 60


def _compliance_overdue_open_count(db: Session) -> int:
    rows = db.scalars(
        select(ComplianceViolation).where(ComplianceViolation.status.in_(["open", "acknowledged"]))
    ).all()
    now = datetime.utcnow()
    overdue = 0
    for r in rows:
        if r.created_at and (now - r.created_at).total_seconds() > _sla_seconds(r.severity):
            overdue += 1
    return overdue


def _get_idempotent_response(db: Session, endpoint: str, key: str | None) -> dict | None:
    if not key:
        return None
    row = db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.endpoint == endpoint,
            ExecutionRequest.idempotency_key == key,
        )
    )
    return row.response_payload if row else None


def _store_idempotent_response(db: Session, endpoint: str, key: str | None, payload: dict) -> None:
    if not key:
        return
    row = ExecutionRequest(endpoint=endpoint, idempotency_key=key, response_payload=payload)
    db.add(row)


@router.get("/mode")
def get_mode(db: Session = Depends(get_db)):
    mode, live_enabled = get_runtime_mode(db)
    return {"mode": mode, "live_trading_enabled": live_enabled}


def _build_live_readiness_payload(db: Session, miro: dict) -> dict:
    overdue = _compliance_overdue_open_count(db)

    checks = {
        "mirofish_live": miro.get("verdict") == "LIVE",
        "compliance_overdue_zero": overdue == 0,
    }
    ready = all(checks.values())

    reasons = []
    if not checks["mirofish_live"]:
        reasons.append("MiroFish not live")
    if not checks["compliance_overdue_zero"]:
        reasons.append(f"{overdue} overdue compliance violations")

    return {
        "ready": ready,
        "checks": checks,
        "reasons": reasons,
        "compliance_overdue_open": overdue,
        "mirofish": {
            "verdict": miro.get("verdict"),
            "provider_mode": miro.get("provider_mode"),
            "readiness_score": miro.get("readiness_score"),
            "live_error": miro.get("live_error"),
            "recommendations": miro.get("recommendations") or [],
        },
    }


def _has_readiness_snapshot_table(db: Session) -> bool:
    try:
        bind = db.get_bind()
        if inspect(bind).has_table("live_readiness_snapshots"):
            return True
        LiveReadinessSnapshot.__table__.create(bind=bind, checkfirst=True)
        return inspect(bind).has_table("live_readiness_snapshots")
    except Exception:
        return False


def _persist_live_readiness_snapshot(db: Session, readiness: dict, source: str) -> LiveReadinessSnapshot | None:
    if not _has_readiness_snapshot_table(db):
        return None

    snapshot = LiveReadinessSnapshot(
        source=source,
        ready=bool(readiness.get("ready", False)),
        checks=readiness.get("checks") or {},
        reasons=readiness.get("reasons") or [],
        compliance_overdue_open=int(readiness.get("compliance_overdue_open") or 0),
        mirofish=readiness.get("mirofish") or {},
    )
    db.add(snapshot)
    db.flush()
    return snapshot


@router.get("/live-readiness", response_model=LiveReadinessResponse)
async def live_readiness(
    ticker: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "analyst", "trader")),
):
    miro = await mirofish_diagnostics({"ticker": ticker} if ticker else {})
    readiness = _build_live_readiness_payload(db, miro)
    _persist_live_readiness_snapshot(db, readiness, source="manual_check")
    db.commit()
    return readiness


@router.put("/mode")
async def update_mode(
    payload: ModeUpdateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin")),
):
    try:
        validate_mode_transition(payload.mode, payload.live_trading_enabled, payload.confirmation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    readiness = None
    if payload.mode == "live" and payload.live_trading_enabled:
        miro = await mirofish_diagnostics({"ticker": payload.ticker} if payload.ticker else {})
        readiness = _build_live_readiness_payload(db, miro)
        _persist_live_readiness_snapshot(db, readiness, source="live_mode_update")
        if not readiness["ready"] and not payload.force_enable_live:
            db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Live readiness checks failed",
                    "reasons": readiness["reasons"],
                    "checks": readiness["checks"],
                },
            )

    row = set_runtime_mode(
        db,
        mode=payload.mode,
        live_enabled=payload.live_trading_enabled,
        changed_by=payload.changed_by,
    )
    log_event(
        db,
        "MODE_CHANGE",
        {
            "mode": row.mode,
            "live_trading_enabled": row.live_enabled,
            "changed_by": payload.changed_by,
            "force_enable_live": payload.force_enable_live,
            "live_readiness": readiness,
        },
        actor=payload.changed_by,
    )
    return {
        "mode": row.mode,
        "live_trading_enabled": row.live_enabled,
        "changed_by": row.changed_by,
        "live_readiness": readiness,
    }


@router.post("/validate")
def validate_execution(payload: OrderRequest, db: Session = Depends(get_db)):
    mode, live_enabled = get_runtime_mode(db)
    order = payload.model_dump(exclude_none=True)
    adapter = AdapterFactory.get_adapter(mode)
    ok, reason = adapter.validate_order(order)

    policy = get_or_create_risk_policy(db)
    hard_constraints = policy.hard_constraints
    if mode == "live":
        hard_constraints = {
            **hard_constraints,
            "max_capital_per_trade": hard_constraints.get("max_capital_per_trade", 2000) * 0.5,
            "max_daily_loss": hard_constraints.get("max_daily_loss", 500) * 0.5,
        }

    risk = RiskEngine(hard_constraints)
    hard_ok, reasons = risk.hard_gate(order, RiskState(kill_switch=bool(hard_constraints.get("kill_switch", False))))
    if mode == "live" and not live_enabled:
        hard_ok = False
        reasons.append("LIVE_DISABLED")

    if not ok:
        record_violation(
            db,
            policy_name="pre_trade_controls",
            rule_code="ADAPTER_VALIDATION_FAILED",
            severity="medium",
            symbol=order.get("symbol"),
            details={"adapter_reason": reason, "mode": mode},
        )

    if not hard_ok:
        record_violation(
            db,
            policy_name="pre_trade_controls",
            rule_code="HARD_RISK_GATE_BLOCK",
            severity="high",
            symbol=order.get("symbol"),
            details={"hard_reasons": reasons, "mode": mode},
        )

    return {
        "mode": mode,
        "live_trading_enabled": live_enabled,
        "adapter_ok": ok,
        "adapter_reason": reason,
        "hard_ok": hard_ok,
        "hard_reasons": reasons,
    }


@router.post("/order")
async def submit_order(
    payload: OrderRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader")),
):
    mode, live_enabled = get_runtime_mode(db)
    order = payload.model_dump(exclude_none=True)

    replay = _get_idempotent_response(db, "/execution/order", payload.idempotency_key)
    if replay:
        return {**replay, "idempotent_replay": True}

    if mode == "live" and not live_enabled:
        record_violation(
            db,
            policy_name="pre_trade_controls",
            rule_code="LIVE_DISABLED",
            severity="critical",
            symbol=order.get("symbol"),
            details={"mode": mode},
        )
        raise HTTPException(status_code=403, detail="Live trading disabled")

    adapter = AdapterFactory.get_adapter(mode)
    ok, reason = adapter.validate_order(order)
    if not ok:
        record_violation(
            db,
            policy_name="pre_trade_controls",
            rule_code="ADAPTER_VALIDATION_FAILED",
            severity="medium",
            symbol=order.get("symbol"),
            details={"adapter_reason": reason, "mode": mode},
        )
        return {"status": "blocked", "reason": reason}

    policy = get_or_create_risk_policy(db)
    hard_constraints = policy.hard_constraints
    if mode == "live":
        hard_constraints = {
            **hard_constraints,
            "max_capital_per_trade": hard_constraints.get("max_capital_per_trade", 2000) * 0.5,
            "max_daily_loss": hard_constraints.get("max_daily_loss", 500) * 0.5,
        }

    risk = RiskEngine(hard_constraints)
    hard_ok, reasons = risk.hard_gate(order, RiskState(kill_switch=bool(hard_constraints.get("kill_switch", False))))
    if not hard_ok:
        record_violation(
            db,
            policy_name="pre_trade_controls",
            rule_code="HARD_RISK_GATE_BLOCK",
            severity="high",
            symbol=order.get("symbol"),
            details={"hard_reasons": reasons, "mode": mode},
        )
        return {"status": "blocked", "reason": "risk_gate", "hard_reasons": reasons}

    result = await adapter.submit_order(order)

    if mode == "paper":
        db.add(
            PaperOrder(
                broker_order_id=result.get("id"),
                ticker=(order.get("symbol") or "").upper(),
                side=order.get("side", "buy"),
                qty=float(order.get("qty", 0) or 0),
                order_type=order.get("type", "market"),
                status=result.get("status", "submitted"),
                rationale=order.get("rationale"),
            )
        )

    journal = TradeJournal(
        ticker=(order.get("symbol") or "").upper(),
        mode=mode,
        recommendation=order.get("recommendation"),
        execution={
            "submitted_at": datetime.utcnow().isoformat(),
            "request": order,
            "result": result,
            "broker_order_id": result.get("id"),
        },
        outcome=None,
        tags={"state": "submitted", "source": "execution/order"},
    )
    db.add(journal)
    db.flush()

    response_payload = {**result, "journal_id": journal.id}
    _store_idempotent_response(db, "/execution/order", payload.idempotency_key, response_payload)

    db.commit()
    db.refresh(journal)

    log_event(db, "ORDER_SUBMIT", {"mode": mode, "payload": order, "result": result, "journal_id": journal.id})
    return response_payload


@router.post("/order/fill")
def handle_order_fill(
    payload: OrderFillRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader")),
):
    fill = payload.model_dump(exclude_none=True)

    replay = _get_idempotent_response(db, "/execution/order/fill", payload.idempotency_key)
    if replay:
        return {**replay, "idempotent_replay": True}

    response_payload = apply_fill_update(db, fill)
    _store_idempotent_response(db, "/execution/order/fill", payload.idempotency_key, response_payload)
    db.commit()

    log_event(db, "ORDER_FILL_UPDATE", fill)
    return response_payload


@router.get("/live-readiness/history", response_model=LiveReadinessTrendResponse)
def live_readiness_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "analyst", "trader")),
):
    if not _has_readiness_snapshot_table(db):
        return LiveReadinessTrendResponse(latest=None, snapshots=[])

    safe_limit = min(max(limit, 1), 500)
    rows = db.scalars(
        select(LiveReadinessSnapshot).order_by(LiveReadinessSnapshot.created_at.desc()).limit(safe_limit)
    ).all()

    snapshots = [
        LiveReadinessSnapshotResponse(
            id=row.id,
            source=row.source,
            ready=row.ready,
            checks=row.checks or {},
            reasons=row.reasons or [],
            compliance_overdue_open=row.compliance_overdue_open,
            mirofish=row.mirofish or {},
            created_at=row.created_at,
        )
        for row in rows
    ]

    latest = snapshots[0] if snapshots else None
    return LiveReadinessTrendResponse(latest=latest, snapshots=snapshots)


@router.get("/readiness-history")
def readiness_history_legacy(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "analyst", "trader")),
):
    if not _has_readiness_snapshot_table(db):
        return {"latest": None, "snapshots": []}

    safe_limit = min(max(limit, 1), 500)
    rows = db.scalars(
        select(LiveReadinessSnapshot).order_by(LiveReadinessSnapshot.created_at.desc()).limit(safe_limit)
    ).all()

    def _row_payload(row: LiveReadinessSnapshot) -> dict:
        readiness = {
            "ready": row.ready,
            "checks": row.checks or {},
            "reasons": row.reasons or [],
            "compliance_overdue_open": row.compliance_overdue_open,
            "mirofish": row.mirofish or {},
        }
        return {
            "id": row.id,
            "source": row.source,
            "created_at": row.created_at,
            "readiness": readiness,
            **readiness,
        }

    snapshots = [_row_payload(r) for r in rows]
    return {
        "latest": snapshots[0] if snapshots else None,
        "snapshots": snapshots,
    }


@router.get("/live-readiness/summary")
def live_readiness_summary(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "analyst", "trader")),
):
    if not _has_readiness_snapshot_table(db):
        return {
            "total": 0,
            "pass_count": 0,
            "fail_count": 0,
            "pass_rate": 0.0,
            "by_source": {},
            "latest_at": None,
        }

    safe_limit = min(max(limit, 1), 1000)
    rows = db.scalars(
        select(LiveReadinessSnapshot).order_by(LiveReadinessSnapshot.created_at.desc()).limit(safe_limit)
    ).all()

    total = len(rows)
    pass_count = sum(1 for r in rows if r.ready)
    fail_count = total - pass_count
    by_source: dict[str, dict[str, int]] = {}
    for r in rows:
        src = r.source or "unknown"
        bucket = by_source.setdefault(src, {"total": 0, "pass": 0, "fail": 0})
        bucket["total"] += 1
        if r.ready:
            bucket["pass"] += 1
        else:
            bucket["fail"] += 1

    return {
        "total": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": round((pass_count / total) if total else 0.0, 4),
        "by_source": by_source,
        "latest_at": rows[0].created_at if rows else None,
    }


@router.get("/analytics")
def execution_analytics(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: str = Depends(require_roles("admin", "trader", "analyst")),
):
    safe_limit = min(max(limit, 10), 500)
    rows = db.scalars(select(TradeJournal).order_by(TradeJournal.id.desc()).limit(safe_limit)).all()

    total = len(rows)
    closed_states = {"filled", "closed"}
    in_flight_states = {"submitted", "partial"}

    closed = 0
    open_positions = 0
    realized_pnl = 0.0
    closed_with_pnl = 0
    winning_closed = 0
    exposure_open = 0.0
    largest_open_notional = 0.0

    for r in rows:
        outcome = r.outcome or {}
        tags = r.tags or {}
        state = outcome.get("state") or (tags.get("state") if isinstance(tags, dict) else None) or "submitted"
        execution = r.execution or {}
        req = execution.get("request") or {}

        qty = float(req.get("qty") or outcome.get("fill_qty") or 0.0)
        fill_price = float(outcome.get("fill_price") or 0.0)
        inferred_notional = float(req.get("notional") or (qty * fill_price) or 0.0)

        if state in closed_states:
            closed += 1
            pnl = outcome.get("pnl")
            if pnl is not None:
                pnl_val = float(pnl)
                realized_pnl += pnl_val
                closed_with_pnl += 1
                if pnl_val > 0:
                    winning_closed += 1
        if state in in_flight_states:
            open_positions += 1
            exposure_open += inferred_notional
            largest_open_notional = max(largest_open_notional, inferred_notional)

    fill_rate = (closed / total) if total else 0.0
    win_rate = (winning_closed / closed_with_pnl) if closed_with_pnl else 0.0

    policy = get_or_create_risk_policy(db)
    hard = policy.hard_constraints or {}
    max_trade = float(hard.get("max_capital_per_trade") or 0.0)
    max_daily_loss = float(hard.get("max_daily_loss") or 0.0)
    max_positions = float(hard.get("max_concurrent_positions") or 0.0)

    risk_utilization = {
        "capital_per_trade_pct": round((largest_open_notional / max_trade) if max_trade else 0.0, 4),
        "daily_loss_pct": round((max(0.0, -realized_pnl) / max_daily_loss) if max_daily_loss else 0.0, 4),
        "concurrent_positions_pct": round((open_positions / max_positions) if max_positions else 0.0, 4),
    }

    mode_rows = db.scalars(select(ExecutionMode).order_by(ExecutionMode.id.desc()).limit(20)).all()
    mode_timeline = [
        {
            "mode": m.mode,
            "live_enabled": m.live_enabled,
            "changed_by": m.changed_by,
            "changed_at": m.changed_at,
        }
        for m in mode_rows
    ]

    audit_rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.event_type.in_(["MODE_CHANGE", "ORDER_SUBMIT", "ORDER_FILL_UPDATE"]))
        .order_by(AuditLog.id.desc())
        .limit(30)
    ).all()
    recent_events = [
        {
            "event_type": a.event_type,
            "actor": a.actor,
            "payload": a.payload,
            "created_at": a.created_at,
        }
        for a in audit_rows
    ]

    return {
        "summary": {
            "journal_entries": total,
            "closed_trades": closed,
            "open_positions": open_positions,
            "fill_rate": round(fill_rate, 4),
            "win_rate": round(win_rate, 4),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": 0.0,
            "open_exposure": round(exposure_open, 2),
        },
        "risk_constraints": hard,
        "risk_utilization": risk_utilization,
        "mode_timeline": mode_timeline,
        "recent_events": recent_events,
    }
