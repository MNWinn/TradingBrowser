from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.core.config import settings


def _normalize_ticker(t: str) -> str:
    return (t or "").strip().upper()


def _valid_ticker(t: str) -> bool:
    if not t:
        return False
    return t.replace(".", "").isalnum() and 1 <= len(t) <= 8


def _env_focus_tickers() -> set[str]:
    raw = settings.mirofish_focus_tickers or ""
    out: set[str] = set()
    for tok in raw.split(","):
        s = _normalize_ticker(tok)
        if _valid_ticker(s):
            out.add(s)
    return out


_STATE: dict[str, Any] = {
    "tickers": _env_focus_tickers(),
    "enabled": True,
    "interval_sec": 240,
    "last_cycle_at": None,
    "results": {},
    "errors": {},
    "runs": 0,
}

_LOCK = RLock()


def get_focus_config() -> dict[str, Any]:
    with _LOCK:
        return {
            "tickers": sorted(list(_STATE["tickers"])),
            "enabled": bool(_STATE["enabled"]),
            "interval_sec": int(_STATE["interval_sec"]),
            "last_cycle_at": _STATE["last_cycle_at"],
            "runs": int(_STATE["runs"]),
            "results": _STATE["results"],
            "errors": _STATE["errors"],
        }


def is_focus_ticker(ticker: str) -> bool:
    t = _normalize_ticker(ticker)
    with _LOCK:
        return t in _STATE["tickers"]


def set_focus_config(tickers: list[str] | None = None, enabled: bool | None = None, interval_sec: int | None = None) -> dict[str, Any]:
    with _LOCK:
        if tickers is not None:
            cleaned = {_normalize_ticker(t) for t in tickers}
            _STATE["tickers"] = {t for t in cleaned if _valid_ticker(t)}
        if enabled is not None:
            _STATE["enabled"] = bool(enabled)
        if interval_sec is not None:
            _STATE["interval_sec"] = max(30, min(int(interval_sec), 3600))
    return get_focus_config()


def add_focus_ticker(ticker: str) -> dict[str, Any]:
    t = _normalize_ticker(ticker)
    if not _valid_ticker(t):
        raise ValueError("Invalid ticker")
    with _LOCK:
        _STATE["tickers"].add(t)
    return get_focus_config()


def remove_focus_ticker(ticker: str) -> dict[str, Any]:
    t = _normalize_ticker(ticker)
    with _LOCK:
        _STATE["tickers"].discard(t)
    return get_focus_config()


def snapshot_for_runner() -> tuple[bool, int, list[str]]:
    with _LOCK:
        return bool(_STATE["enabled"]), int(_STATE["interval_sec"]), sorted(list(_STATE["tickers"]))


def update_focus_result(ticker: str, result: dict | None = None, error: str | None = None) -> None:
    t = _normalize_ticker(ticker)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        if result is not None:
            _STATE["results"][t] = {
                "at": now,
                "overall_bias": result.get("overall_bias"),
                "overall_confidence": result.get("overall_confidence"),
                "alignment_score": result.get("alignment_score"),
                "provider_mode": result.get("provider_mode"),
            }
        if error:
            _STATE["errors"][t] = {"at": now, "error": error[:240]}


def mark_cycle() -> None:
    with _LOCK:
        _STATE["last_cycle_at"] = datetime.now(timezone.utc).isoformat()
        _STATE["runs"] = int(_STATE["runs"]) + 1
