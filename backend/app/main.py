import asyncio
import json
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
# ensure model registry is imported for create_all
from app import models  # noqa: F401

from app.routers import (
    watchlist,
    market,
    chart,
    signals,
    mirofish,
    swarm,
    agents,
    risk,
    execution,
    alpaca,
    training,
    evaluation,
    strategies,
    audit,
    journal,
    settings as settings_router,
    compliance,
    practice,
)
from app.services.agent_api import router as agent_fleet_router
from app.services.focus_runner import focus_runner_loop
from app.services.market_data import (
    alpaca_ws_url,
    configured_live_data,
    get_quote_snapshot,
    normalize_alpaca_ws_event,
)

try:
    import websockets
except Exception:  # pragma: no cover - optional runtime dependency
    websockets = None

app = FastAPI(title="TradingBrowser API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(watchlist.router)
app.include_router(market.router)
app.include_router(chart.router)
app.include_router(signals.router)
app.include_router(mirofish.router)
app.include_router(swarm.router)
app.include_router(agents.router)
app.include_router(risk.router)
app.include_router(execution.router)
app.include_router(alpaca.router)
app.include_router(training.router)
app.include_router(evaluation.router)
app.include_router(strategies.router)
app.include_router(audit.router)
app.include_router(journal.router)
app.include_router(settings_router.router)
app.include_router(compliance.router)
app.include_router(practice.router)
app.include_router(agent_fleet_router)


@app.on_event("startup")
async def startup() -> None:
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)

    app.state.focus_runner_stop = asyncio.Event()
    app.state.focus_runner_task = asyncio.create_task(focus_runner_loop(app.state.focus_runner_stop))


@app.on_event("shutdown")
async def shutdown() -> None:
    stop = getattr(app.state, "focus_runner_stop", None)
    task = getattr(app.state, "focus_runner_task", None)
    if stop is not None:
        stop.set()
    if task is not None:
        try:
            await task
        except Exception:
            pass


@app.get("/")
def root():
    return {"name": "TradingBrowser API", "status": "ok"}


@app.websocket("/ws/market")
async def market_ws(ws: WebSocket):
    await ws.accept()
    tickers = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]

    # Try true streaming from Alpaca first.
    if configured_live_data() and websockets is not None:
        try:
            url = alpaca_ws_url()
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as alp_ws:
                await alp_ws.send(
                    json.dumps({"action": "auth", "key": settings.alpaca_api_key, "secret": settings.alpaca_api_secret})
                )
                await alp_ws.send(json.dumps({"action": "subscribe", "trades": tickers, "quotes": tickers}))

                last_price: dict[str, float] = {}
                prev_close: dict[str, float] = {}

                # prime previous close/change context from snapshots
                for t in tickers:
                    snap = get_quote_snapshot(t)
                    if not snap.get("simulated"):
                        last_price[t] = float(snap.get("price") or 0.0)
                        pc = float(snap.get("price") or 0.0) / (1 + (float(snap.get("change_pct") or 0.0) / 100)) if snap.get("change_pct") is not None else 0.0
                        if pc > 0:
                            prev_close[t] = pc

                while True:
                    raw = await asyncio.wait_for(alp_ws.recv(), timeout=30)
                    events = json.loads(raw)
                    if isinstance(events, dict):
                        events = [events]
                    for ev in events:
                        payload = normalize_alpaca_ws_event(ev, last_price=last_price, prev_close=prev_close)
                        if payload:
                            await ws.send_json(payload)
        except Exception:
            # fall through to snapshot polling
            pass

    # Fallback path: periodic snapshots (live REST or simulated)
    i = 0
    try:
        while True:
            ticker = tickers[i % len(tickers)]
            payload = get_quote_snapshot(ticker)
            if not payload.get("ts"):
                payload["ts"] = datetime.utcnow().isoformat()
            await ws.send_json(payload)
            i += 1
            await asyncio.sleep(0.8)
    except WebSocketDisconnect:
        return
