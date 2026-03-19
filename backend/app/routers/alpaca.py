from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.config import settings
from app.core.database import get_db
from sqlalchemy import select

from app.models.entities import ExecutionRequest
from app.schemas.execution import OrderFillRequest
from app.services.audit import log_event
from app.services.execution import AlpacaPaperAdapter
from app.services.orders import apply_fill_update
from app.services.webhook import verify_alpaca_signature

router = APIRouter(prefix="/alpaca", tags=["alpaca"])


@router.get("/account")
async def account(_: str = Depends(require_roles("admin", "trader", "analyst"))):
    adapter = AlpacaPaperAdapter()
    return await adapter.get_account_state()


@router.get("/orders")
async def orders(status: str = "all", limit: int = 50, _: str = Depends(require_roles("admin", "trader", "analyst"))):
    adapter = AlpacaPaperAdapter()
    return await adapter.list_orders(status=status, limit=limit)


@router.post("/webhook/order-update")
async def alpaca_order_update_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw = await request.body()
    signature = request.headers.get("x-alpaca-signature")

    if not verify_alpaca_signature(raw, signature, settings.alpaca_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    order = payload.get("order", {})

    key = f"alpaca:{order.get('id')}:{order.get('status')}"
    existing = db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.endpoint == "/alpaca/webhook/order-update",
            ExecutionRequest.idempotency_key == key,
        )
    )
    if existing:
        return {**existing.response_payload, "idempotent_replay": True}

    fill_payload = OrderFillRequest(
        broker_order_id=order.get("id"),
        state=order.get("status", "filled"),
        fill_price=float(order.get("filled_avg_price") or 0) if order.get("filled_avg_price") else None,
        fill_qty=float(order.get("filled_qty") or 0) if order.get("filled_qty") else None,
        notes="alpaca_webhook",
    ).model_dump(exclude_none=True)

    result = apply_fill_update(db, fill_payload)
    db.add(
        ExecutionRequest(
            endpoint="/alpaca/webhook/order-update",
            idempotency_key=key,
            response_payload=result,
        )
    )
    db.commit()
    log_event(db, "ALPACA_WEBHOOK_ORDER_UPDATE", payload)
    return result
