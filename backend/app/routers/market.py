from fastapi import APIRouter

from app.services.market_data import get_bars_snapshot, get_quote_snapshot, market_data_status

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/quote/{ticker}")
def quote(ticker: str):
    return get_quote_snapshot(ticker)


@router.get("/bars/{ticker}")
def bars(ticker: str, timeframe: str = "1m", limit: int = 200):
    return get_bars_snapshot(ticker=ticker, timeframe=timeframe, limit=limit)


@router.get("/source")
def source_status():
    return market_data_status()
