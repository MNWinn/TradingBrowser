from __future__ import annotations

import asyncio

from app.services.focus_runtime import mark_cycle, snapshot_for_runner, update_focus_result
from app.services.mirofish import mirofish_deep_swarm


async def run_focus_cycle() -> dict:
    enabled, _interval, tickers = snapshot_for_runner()
    if not enabled or not tickers:
        return {"ran": False, "reason": "disabled_or_empty", "tickers": tickers}

    ran = 0
    for t in tickers:
        try:
            res = await mirofish_deep_swarm({"ticker": t})
            update_focus_result(t, result=res)
        except Exception as e:
            update_focus_result(t, error=str(e))
        ran += 1

    mark_cycle()
    return {"ran": True, "count": ran, "tickers": tickers}


async def focus_runner_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        enabled, interval_sec, tickers = snapshot_for_runner()
        if enabled and tickers:
            await run_focus_cycle()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(15, interval_sec))
        except asyncio.TimeoutError:
            continue
