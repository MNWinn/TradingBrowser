from typing import Any, Literal

from pydantic import BaseModel, Field


ViolationStatus = Literal["open", "acknowledged", "waived", "remediated"]
ViolationSeverity = Literal["low", "medium", "high", "critical"]


class ViolationCreateRequest(BaseModel):
    policy_name: str = "pre_trade_controls"
    rule_code: str
    severity: ViolationSeverity = "medium"
    symbol: str | None = None
    assignee: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ViolationUpdateRequest(BaseModel):
    status: ViolationStatus
    acknowledged_by: str | None = None
    assignee: str | None = None
    resolution_notes: str | None = None


class ViolationBulkUpdateRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)
    status: ViolationStatus
    acknowledged_by: str | None = None
    assignee: str | None = None
    resolution_notes: str | None = None
