from typing import Any, Literal

from pydantic import BaseModel


class BrokerAccountUpsertRequest(BaseModel):
    provider: Literal["alpaca"]
    environment: Literal["paper", "live"]
    account_ref: str | None = None
    credentials: dict[str, Any]


class BrokerAccountView(BaseModel):
    id: int
    provider: str
    environment: str
    account_ref: str | None = None
    credentials_fingerprint: str | None = None
    created_at: str
