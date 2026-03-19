import asyncio
import random
import time
from typing import Any

from app.services.focus_runtime import is_focus_ticker
from app.services.mirofish_service import mirofish_deep_swarm, mirofish_predict


async def market_structure_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "market_structure", "recommendation": "LONG", "confidence": 0.58}


async def technical_signal_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "technical_signal", "recommendation": "LONG", "confidence": 0.62}


async def probability_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "probability", "recommendation": "WATCHLIST", "confidence": 0.54}


async def mirofish_context_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    if is_focus_ticker(ticker):
        m = await mirofish_deep_swarm({"ticker": ticker})
        bias = m.get("overall_bias", "NEUTRAL")
        conf = m.get("overall_confidence", 0.55)
        return {
            "agent": "mirofish_context",
            "recommendation": "LONG" if bias == "BULLISH" else ("NO_TRADE" if bias == "NEUTRAL" else "SHORT"),
            "confidence": conf,
            "context": m,
        }

    m = await mirofish_predict({"ticker": ticker})
    return {
        "agent": "mirofish_context",
        "recommendation": "LONG" if m["directional_bias"] == "BULLISH" else "NO_TRADE",
        "confidence": m["confidence"],
        "context": m,
    }


async def news_catalyst_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "news_catalyst", "recommendation": "WATCHLIST", "confidence": 0.49}


async def risk_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "risk", "recommendation": "ALLOW", "confidence": 0.90}


async def execution_agent(ticker: str, mode: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "execution", "recommendation": "ELIGIBLE" if mode != "research" else "BLOCK", "confidence": 0.95}


async def learning_agent(ticker: str) -> dict:
    await asyncio.sleep(0.05)
    return {"agent": "learning", "recommendation": "TAGGED", "confidence": 1.0}


class SwarmOrchestrator:
    async def run(self, ticker: str, mode: str) -> dict[str, Any]:
        started = time.perf_counter()
        tasks = [
            market_structure_agent(ticker),
            technical_signal_agent(ticker),
            probability_agent(ticker),
            mirofish_context_agent(ticker),
            news_catalyst_agent(ticker),
            risk_agent(ticker),
            execution_agent(ticker, mode),
            learning_agent(ticker),
        ]
        results = await asyncio.gather(*tasks)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        votes = [r["recommendation"] for r in results if r["agent"] not in {"risk", "execution", "learning"}]
        long_votes = sum(v == "LONG" for v in votes)
        watch_votes = sum(v == "WATCHLIST" for v in votes)
        no_trade_votes = sum(v == "NO_TRADE" for v in votes)

        if long_votes >= 3:
            aggregated = "LONG"
        elif no_trade_votes >= 2:
            aggregated = "NO_TRADE"
        else:
            aggregated = "WATCHLIST"

        consensus_score = max(long_votes, watch_votes, no_trade_votes) / max(len(votes), 1)
        disagreement_score = 1 - consensus_score

        return {
            "ticker": ticker,
            "task_id": f"swarm-{ticker}-{random.randint(1000, 9999)}",
            "mode": mode,
            "agent_runs": results,
            "aggregated_recommendation": aggregated,
            "consensus_score": round(consensus_score, 2),
            "disagreement_score": round(disagreement_score, 2),
            "latency_ms": elapsed_ms,
        }
