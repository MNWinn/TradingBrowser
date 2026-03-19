from pydantic import BaseModel


class JournalOutcomeUpdate(BaseModel):
    state: str
    fill_price: float | None = None
    fill_qty: float | None = None
    pnl: float | None = None
    notes: str | None = None
