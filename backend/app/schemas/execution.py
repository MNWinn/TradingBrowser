from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ModeUpdateRequest(BaseModel):
    mode: Literal["research", "paper", "live"]
    live_trading_enabled: bool = False
    confirmation: str | None = None
    force_enable_live: bool = False
    changed_by: str = "system"
    ticker: str | None = None


class OrderRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    qty: float | None = Field(default=None, gt=0)
    notional: float | None = Field(default=None, gt=0)
    type: Literal["market", "limit", "stop", "stop_limit"] = "market"
    stop_loss: float | None = Field(default=None, gt=0)
    rationale: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def check_qty_or_notional(self):
        if self.qty is None and self.notional is None:
            raise ValueError("qty or notional is required")
        return self


class OrderFillRequest(BaseModel):
    broker_order_id: str
    state: Literal["filled", "partial", "closed", "cancelled", "rejected"] = "filled"
    fill_price: float | None = None
    fill_qty: float | None = None
    pnl: float | None = None
    notes: str | None = None
    idempotency_key: str | None = None


class LiveReadinessResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]
    reasons: list[str]
    compliance_overdue_open: int
    mirofish: dict[str, Any]


class LiveReadinessSnapshotResponse(LiveReadinessResponse):
    id: int
    source: str
    created_at: datetime


class LiveReadinessTrendResponse(BaseModel):
    latest: LiveReadinessSnapshotResponse | None
    snapshots: list[LiveReadinessSnapshotResponse]
