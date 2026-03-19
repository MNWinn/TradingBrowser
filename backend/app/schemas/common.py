from pydantic import BaseModel, Field
from typing import Any


class ApiResponse(BaseModel):
    ok: bool = True
    data: Any | None = None
    message: str | None = None


class Recommendation(BaseModel):
    ticker: str
    action: str = Field(description="LONG | SHORT | NO_TRADE | WATCHLIST")
    confidence: float
    consensus_score: float
    disagreement_score: float
    position_size_suggestion: float
    stop_loss: float | None = None
    target: float | None = None
    reason_codes: list[str]
    explanation: str
    execution_eligibility: dict
