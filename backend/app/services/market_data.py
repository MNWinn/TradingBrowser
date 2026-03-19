from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings


def _timeframe_seconds(timeframe: str) -> int:
    mapping = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "1d": 86400,
    }
    return mapping.get(timeframe, 300)


def _alpaca_timeframe(timeframe: str) -> str:
    mapping = {
        "1m": "1Min",
        "5m": "5Min",
        "15m": "15Min",
        "1h": "1Hour",
        "1d": "1Day",
    }
    return mapping.get(timeframe, "5Min")


def configured_live_data() -> bool:
    return bool(settings.alpaca_api_key and settings.alpaca_api_secret)


def market_feed() -> str:
    return (settings.alpaca_data_feed or "iex").lower().strip()


def _feed_candidates() -> list[str]:
    configured = market_feed()
    feeds = [configured]
    if configured != "iex":
        feeds.append("iex")
    return feeds


def alpaca_ws_url() -> str:
    return settings.alpaca_data_ws_sip if market_feed() == "sip" else settings.alpaca_data_ws_iex


def market_data_status() -> dict[str, Any]:
    status = {
        "configured": configured_live_data(),
        "feed": market_feed(),
        "source": "alpaca" if configured_live_data() else "simulated",
        "ws_url": alpaca_ws_url() if configured_live_data() else None,
    }
    if not configured_live_data():
        return status

    # Best-effort connectivity check for easier debugging.
    try:
        headers = _alpaca_headers()
        base = settings.alpaca_data_base_url.rstrip("/")
        with httpx.Client(timeout=4.0) as client:
            res = client.get(
                f"{base}/v2/stocks/AAPL/trades/latest",
                headers=headers,
                params={"feed": _feed_candidates()[0]},
            )
        status["auth_ok"] = res.status_code < 400
        status["http_status"] = res.status_code
        if res.status_code >= 400:
            status["error"] = res.text[:180]
    except Exception as e:
        status["auth_ok"] = False
        status["error"] = str(e)
    return status


def _alpaca_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
    }


def _generate_bars(ticker: str, timeframe: str, limit: int) -> list[dict]:
    symbol = ticker.upper()
    step = _timeframe_seconds(timeframe)
    now = datetime.now(timezone.utc)

    hour_bucket = int(now.timestamp()) // 3600
    rng = random.Random(f"{symbol}:{timeframe}:{hour_bucket}")

    base_price = 70 + (sum(ord(c) for c in symbol) % 250)
    prev_close = float(base_price)

    bars: list[dict] = []
    for i in range(limit):
        ts = now - timedelta(seconds=step * (limit - 1 - i))
        cycle = math.sin((i / max(limit, 1)) * math.pi * 4)
        drift = cycle * 0.35
        noise = rng.uniform(-0.45, 0.45)

        open_price = prev_close
        close_price = max(1.0, open_price + drift + noise)

        wick_up = abs(rng.uniform(0.05, 0.35))
        wick_down = abs(rng.uniform(0.05, 0.35))
        high_price = max(open_price, close_price) + wick_up
        low_price = max(0.5, min(open_price, close_price) - wick_down)
        volume = int(200_000 + rng.randint(0, 1_500_000) * (1 + abs(cycle)))

        bars.append(
            {
                "t": ts.isoformat(),
                "o": round(open_price, 2),
                "h": round(high_price, 2),
                "l": round(low_price, 2),
                "c": round(close_price, 2),
                "v": volume,
            }
        )
        prev_close = close_price

    return bars


def _quote_from_sim(symbol: str) -> dict:
    bars = _generate_bars(symbol, "1m", 2)
    prev_close = bars[0]["c"]
    last = bars[-1]
    price = last["c"]
    change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0

    return {
        "ticker": symbol,
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "volume": last["v"],
        "spread": 0.01,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "simulated",
        "simulated": True,
    }


def _quote_from_snapshot(client: httpx.Client, base: str, symbol: str, feed: str, headers: dict[str, str]) -> dict | None:
    snap = client.get(
        f"{base}/v2/stocks/snapshots",
        headers=headers,
        params={"symbols": symbol, "feed": feed},
    )
    if snap.status_code >= 400:
        return None

    body = snap.json() or {}
    data = (body.get("snapshots") or {}).get(symbol) or {}
    latest_trade = data.get("latestTrade") or {}
    latest_quote = data.get("latestQuote") or {}
    prev_bar = data.get("prevDailyBar") or {}

    price = float(latest_trade.get("p") or 0.0)
    prev_close = float(prev_bar.get("c") or 0.0)
    change_pct = ((price - prev_close) / prev_close) * 100 if (price and prev_close) else 0.0
    bid = float(latest_quote.get("bp") or 0.0)
    ask = float(latest_quote.get("ap") or 0.0)
    spread = max(0.0, ask - bid) if (ask and bid) else 0.01

    if price <= 0:
        return None

    return {
        "ticker": symbol,
        "price": round(price, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(latest_trade.get("s") or 0),
        "spread": round(spread, 4),
        "ts": latest_trade.get("t") or datetime.now(timezone.utc).isoformat(),
        "source": f"alpaca_{feed}",
        "simulated": False,
    }


def _quote_from_latest(client: httpx.Client, base: str, symbol: str, feed: str, headers: dict[str, str]) -> dict | None:
    trade = client.get(f"{base}/v2/stocks/{symbol}/trades/latest", headers=headers, params={"feed": feed})
    quote = client.get(f"{base}/v2/stocks/{symbol}/quotes/latest", headers=headers, params={"feed": feed})
    if trade.status_code >= 400 or quote.status_code >= 400:
        return None

    trade_body = trade.json().get("trade") or {}
    quote_body = quote.json().get("quote") or {}

    price = float(trade_body.get("p") or 0.0)
    bid = float(quote_body.get("bp") or 0.0)
    ask = float(quote_body.get("ap") or 0.0)
    spread = max(0.0, ask - bid) if (ask and bid) else 0.01

    if price <= 0:
        return None

    return {
        "ticker": symbol,
        "price": round(price, 2),
        "change_pct": 0.0,
        "volume": int(trade_body.get("s") or 0),
        "spread": round(spread, 4),
        "ts": trade_body.get("t") or datetime.now(timezone.utc).isoformat(),
        "source": f"alpaca_{feed}",
        "simulated": False,
    }


def get_quote_snapshot(ticker: str) -> dict:
    symbol = ticker.upper()
    if configured_live_data():
        try:
            headers = _alpaca_headers()
            base = settings.alpaca_data_base_url.rstrip("/")
            with httpx.Client(timeout=5.0) as client:
                for feed in _feed_candidates():
                    q = _quote_from_snapshot(client, base, symbol, feed, headers)
                    if q:
                        return q
                for feed in _feed_candidates():
                    q = _quote_from_latest(client, base, symbol, feed, headers)
                    if q:
                        return q
        except Exception:
            pass

    return _quote_from_sim(symbol)


def get_bars_snapshot(ticker: str, timeframe: str = "1m", limit: int = 200) -> dict:
    symbol = ticker.upper()
    safe_limit = min(max(limit, 10), 1000)

    if configured_live_data():
        try:
            headers = _alpaca_headers()
            base = settings.alpaca_data_base_url.rstrip("/")
            tf = _alpaca_timeframe(timeframe)
            with httpx.Client(timeout=6.0) as client:
                for feed in _feed_candidates():
                    res = client.get(
                        f"{base}/v2/stocks/{symbol}/bars",
                        headers=headers,
                        params={"timeframe": tf, "limit": safe_limit, "adjustment": "raw", "feed": feed},
                    )
                    if res.status_code >= 400:
                        continue
                    data = res.json()
                    bars_raw = data.get("bars") or []
                    bars = [
                        {
                            "t": b.get("t"),
                            "o": b.get("o"),
                            "h": b.get("h"),
                            "l": b.get("l"),
                            "c": b.get("c"),
                            "v": b.get("v"),
                        }
                        for b in bars_raw
                    ]
                    if bars:
                        return {
                            "ticker": symbol,
                            "timeframe": timeframe,
                            "bars": bars,
                            "source": f"alpaca_{feed}",
                            "simulated": False,
                        }
        except Exception:
            pass

    return {
        "ticker": symbol,
        "timeframe": timeframe,
        "bars": _generate_bars(ticker=symbol, timeframe=timeframe, limit=safe_limit),
        "source": "simulated",
        "simulated": True,
    }


def normalize_alpaca_ws_event(event: dict[str, Any], last_price: dict[str, float], prev_close: dict[str, float]) -> dict | None:
    et = event.get("T")
    symbol = event.get("S")
    if et not in {"t", "q"} or not symbol:
        return None

    symbol = str(symbol).upper()
    ts = event.get("t") or datetime.now(timezone.utc).isoformat()

    if et == "t":
        price = float(event.get("p") or 0.0)
        size = int(event.get("s") or 0)
        if price > 0:
            last_price[symbol] = price
        pc = prev_close.get(symbol, 0.0)
        change = ((price - pc) / pc) * 100 if (price and pc) else 0.0
        return {
            "ticker": symbol,
            "price": round(price, 2),
            "change_pct": round(change, 2),
            "volume": size,
            "spread": 0.0,
            "ts": ts,
            "source": f"alpaca_ws_{market_feed()}",
            "simulated": False,
        }

    bid = float(event.get("bp") or 0.0)
    ask = float(event.get("ap") or 0.0)
    spread = max(0.0, ask - bid) if (bid and ask) else 0.0
    mid = ((bid + ask) / 2) if (bid and ask) else (ask or bid or last_price.get(symbol, 0.0))
    if mid > 0:
        last_price[symbol] = mid
    pc = prev_close.get(symbol, 0.0)
    change = ((mid - pc) / pc) * 100 if (mid and pc) else 0.0

    return {
        "ticker": symbol,
        "price": round(mid, 2),
        "change_pct": round(change, 2),
        "volume": 0,
        "spread": round(spread, 4),
        "ts": ts,
        "source": f"alpaca_ws_{market_feed()}",
        "simulated": False,
    }


class MarketDataService:
    """Service class for market data operations.
    
    Wraps the existing market data functions for use in practice strategies.
    """
    
    async def get_latest_price(self, ticker: str) -> dict:
        """Get latest price for a ticker."""
        quote = get_quote_snapshot(ticker)
        return {
            "ticker": ticker,
            "price": quote.get("price", 0.0),
            "bid": quote.get("bid", 0.0),
            "ask": quote.get("ask", 0.0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_bars(self, ticker: str, timeframe: str = "5m", limit: int = 100) -> dict:
        """Get historical bars for a ticker."""
        return get_bars_snapshot(ticker, timeframe, limit)
    
    async def get_quote(self, ticker: str) -> dict:
        """Get current quote for a ticker."""
        return get_quote_snapshot(ticker)
