from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.focus_runtime import get_focus_config, is_focus_ticker


def _stub_response(payload: dict, reason: str = "stub") -> dict:
    return {
        "provider": "mirofish",
        "provider_mode": "stub",
        "reason": reason,
        "ticker": payload.get("ticker"),
        "directional_bias": "BULLISH",
        "confidence": 0.61,
        "scenario_summary": "Recent narrative and event flow supports upside continuation.",
        "catalyst_summary": "Earnings sentiment and sector momentum positive.",
        "risk_flags": ["macro_event_within_24h"],
        "leaning": "TRADE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _headers() -> dict:
    if settings.mirofish_api_key:
        return {
            "Authorization": f"Bearer {settings.mirofish_api_key}",
            "Content-Type": "application/json",
        }
    return {"Content-Type": "application/json"}


async def _request_json(client: httpx.AsyncClient, method: str, path: str, payload: dict | None = None) -> tuple[int, dict | list | str]:
    url = f"{settings.mirofish_base_url.rstrip('/')}{path}"
    res = await client.request(method, url, json=payload, headers=_headers())
    try:
        body = res.json()
    except Exception:
        body = res.text
    return res.status_code, body


def _extract_bias_from_text(text: str) -> tuple[str, float]:
    t = (text or "").lower()
    bullish = ["bull", "up", "long", "上涨", "看多", "多头"]
    bearish = ["bear", "down", "short", "下跌", "看空", "空头"]

    bull_hits = sum(k in t for k in bullish)
    bear_hits = sum(k in t for k in bearish)

    if bull_hits > bear_hits:
        return "BULLISH", min(0.55 + 0.07 * (bull_hits - bear_hits), 0.9)
    if bear_hits > bull_hits:
        return "BEARISH", min(0.55 + 0.07 * (bear_hits - bull_hits), 0.9)
    return "NEUTRAL", 0.5


def mirofish_status() -> dict:
    configured = bool(settings.mirofish_base_url)
    focused = get_focus_config().get("tickers", [])
    return {
        "configured": configured,
        "provider": "mirofish",
        "base_url": settings.mirofish_base_url or None,
        "mode": "live" if configured else "stub",
        "simulation_id": settings.mirofish_simulation_id or None,
        "focus_tickers": focused,
        "note": "Set MIROFISH_BASE_URL to enable live calls. Focus tickers can be changed at runtime via /swarm/focus.",
    }


def _body_error(body: dict | list | str) -> str:
    if isinstance(body, dict):
        if isinstance(body.get("error"), str):
            return body["error"]
        if isinstance(body.get("detail"), str):
            return body["detail"]
        if isinstance(body.get("message"), str):
            return body["message"]
        return json.dumps(body, ensure_ascii=False)[:260]
    if isinstance(body, list):
        return json.dumps(body, ensure_ascii=False)[:260]
    return str(body)[:260]


async def _predict_via_direct_endpoint_verbose(client: httpx.AsyncClient, payload: dict) -> tuple[dict | None, str | None]:
    status_code, body = await _request_json(client, "POST", "/predict", payload)
    if status_code >= 400:
        return None, f"/predict {status_code}: {_body_error(body)}"
    if isinstance(body, dict):
        return {
            **body,
            "provider": body.get("provider", "mirofish"),
            "provider_mode": "live",
            "timestamp": body.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }, None
    return None, "/predict returned non-object payload"


async def _resolve_simulation_id(client: httpx.AsyncClient) -> str | None:
    if settings.mirofish_simulation_id:
        return settings.mirofish_simulation_id

    status_code, body = await _request_json(client, "GET", "/api/simulation/history?limit=1")
    if status_code >= 400 or not isinstance(body, dict):
        return None

    items = body.get("data") or []
    if not items:
        return None
    return items[0].get("simulation_id")


def _bridge_prompt(payload: dict) -> str:
    ticker = payload.get("ticker", "UNKNOWN")
    timeframe = payload.get("timeframe", "5m")
    lens = payload.get("lens", "overall")
    focus_context = payload.get("focus_context", "")
    objective = payload.get("objective", "short-term directional read")

    return (
        "Return a concise directional market read in JSON-like prose. "
        "Include directional bias (BULLISH/BEARISH/NEUTRAL), confidence (0-1), key catalyst, and key risk. "
        f"Objective: {objective}. Lens: {lens}. Ticker: {ticker}. Timeframe: {timeframe}. "
        f"Focus context: {focus_context or 'none'}."
    )


async def _predict_via_oss_chat_bridge_verbose(client: httpx.AsyncClient, payload: dict) -> tuple[dict | None, str | None]:
    simulation_id = await _resolve_simulation_id(client)
    if not simulation_id:
        return None, "no simulation_id available for /api/report/chat"

    ticker = payload.get("ticker", "UNKNOWN")
    prompt = _bridge_prompt(payload)

    status_code, body = await _request_json(
        client,
        "POST",
        "/api/report/chat",
        {"simulation_id": simulation_id, "message": prompt, "chat_history": []},
    )
    if status_code >= 400:
        return None, f"/api/report/chat {status_code}: {_body_error(body)}"
    if not isinstance(body, dict):
        return None, "/api/report/chat returned non-object payload"

    response_text = (
        body.get("data", {}).get("response")
        if isinstance(body.get("data"), dict)
        else json.dumps(body, ensure_ascii=False)
    ) or ""

    bias, confidence = _extract_bias_from_text(response_text)

    catalyst = "Signal derived from MiroFish report chat bridge"
    risk = "Model response may be qualitative"

    m_cat = re.search(r"(?:catalyst|催化|驱动)[:：]\s*(.+)", response_text, flags=re.IGNORECASE)
    if m_cat:
        catalyst = m_cat.group(1).strip()[:220]

    m_risk = re.search(r"(?:risk|风险)[:：]\s*(.+)", response_text, flags=re.IGNORECASE)
    if m_risk:
        risk = m_risk.group(1).strip()[:220]

    return {
        "provider": "mirofish",
        "provider_mode": "live_chat_bridge",
        "ticker": ticker,
        "directional_bias": bias,
        "confidence": round(confidence, 2),
        "scenario_summary": response_text[:700] if response_text else "No response summary.",
        "catalyst_summary": catalyst,
        "risk_flags": [risk],
        "leaning": "TRADE" if bias in {"BULLISH", "BEARISH"} else "WAIT",
        "simulation_id": simulation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, None


async def _predict_with_client(client: httpx.AsyncClient, payload: dict) -> dict:
    errors: list[str] = []

    direct, direct_error = await _predict_via_direct_endpoint_verbose(client, payload)
    if direct:
        return direct
    if direct_error:
        errors.append(direct_error)

    bridged, bridge_error = await _predict_via_oss_chat_bridge_verbose(client, payload)
    if bridged:
        return bridged
    if bridge_error:
        errors.append(bridge_error)

    return {
        **_stub_response(payload, reason="mirofish_no_compatible_endpoint"),
        "provider_mode": "fallback_stub",
        "live_error": " | ".join(errors) if errors else "MiroFish endpoint compatibility unresolved",
    }


async def mirofish_predict(payload: dict) -> dict:
    status = mirofish_status()
    if not status["configured"]:
        return _stub_response(payload, reason="mirofish_not_configured")

    try:
        async with httpx.AsyncClient(timeout=settings.mirofish_timeout_sec) as client:
            return await _predict_with_client(client, payload)
    except Exception as e:
        return {
            **_stub_response(payload, reason="mirofish_exception"),
            "provider_mode": "fallback_stub",
            "live_error": str(e),
        }


async def mirofish_deep_swarm(payload: dict) -> dict:
    ticker = str(payload.get("ticker") or "").upper()
    if not ticker:
        return {
            **_stub_response(payload, reason="missing_ticker"),
            "provider_mode": "fallback_stub",
            "deep": True,
            "analyses": [],
        }

    status = mirofish_status()
    if not status["configured"]:
        return {
            **_stub_response({**payload, "ticker": ticker}, reason="mirofish_not_configured"),
            "provider_mode": "stub",
            "deep": True,
            "analyses": [],
        }

    focus = is_focus_ticker(ticker)
    timeframes = payload.get("timeframes") or (["1m", "5m", "15m", "1h"] if focus else ["5m", "15m", "1h"])
    lenses = payload.get("lenses") or (["trend", "momentum", "catalyst", "risk"] if focus else ["trend", "risk", "catalyst"])
    focus_context = payload.get("focus_context") or ("priority watchlist ticker" if focus else "")

    analyses: list[dict] = []
    max_analyses = 16

    try:
        async with httpx.AsyncClient(timeout=settings.mirofish_timeout_sec) as client:
            for tf in timeframes:
                for lens in lenses:
                    if len(analyses) >= max_analyses:
                        break
                    result = await _predict_with_client(
                        client,
                        {
                            "ticker": ticker,
                            "timeframe": tf,
                            "lens": lens,
                            "focus_context": focus_context,
                            "objective": "in-depth multi-lens swarm decision support",
                        },
                    )
                    analyses.append(
                        {
                            "timeframe": tf,
                            "lens": lens,
                            "bias": result.get("directional_bias", "NEUTRAL"),
                            "confidence": float(result.get("confidence") or 0.5),
                            "summary": result.get("scenario_summary"),
                            "catalyst": result.get("catalyst_summary"),
                            "risk_flags": result.get("risk_flags") or [],
                            "provider_mode": result.get("provider_mode"),
                        }
                    )
                if len(analyses) >= max_analyses:
                    break
    except Exception as e:
        return {
            **_stub_response({**payload, "ticker": ticker}, reason="mirofish_exception"),
            "provider_mode": "fallback_stub",
            "deep": True,
            "live_error": str(e),
            "analyses": analyses,
        }

    if not analyses:
        return {
            **_stub_response({**payload, "ticker": ticker}, reason="no_deep_analyses"),
            "provider_mode": "fallback_stub",
            "deep": True,
            "analyses": [],
        }

    votes = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    for a in analyses:
        b = a["bias"] if a["bias"] in votes else "NEUTRAL"
        votes[b] += 1

    overall_bias = max(votes, key=votes.get)
    avg_conf = sum(a["confidence"] for a in analyses) / max(len(analyses), 1)
    aligned = [a["confidence"] for a in analyses if a["bias"] == overall_bias]
    overall_conf = (sum(aligned) / len(aligned)) if aligned else avg_conf
    alignment_score = votes[overall_bias] / len(analyses)

    return {
        "provider": "mirofish",
        "provider_mode": "deep_live",
        "deep": True,
        "ticker": ticker,
        "focused": focus,
        "overall_bias": overall_bias,
        "overall_confidence": round(overall_conf, 3),
        "alignment_score": round(alignment_score, 3),
        "votes": votes,
        "timeframes": timeframes,
        "lenses": lenses,
        "analyses": analyses,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def mirofish_diagnostics(payload: dict | None = None) -> dict:
    payload = payload or {}
    ticker = (payload.get("ticker") or "AAPL").upper()

    base = mirofish_status()
    if not base.get("configured"):
        return {
            **base,
            "verdict": "NOT_CONFIGURED",
            "readiness_score": 0,
            "can_use_live": False,
            "checks": [],
            "recommendations": [
                "Set MIROFISH_BASE_URL",
                "Set MIROFISH_API_KEY if upstream requires auth",
            ],
        }

    checks: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=settings.mirofish_timeout_sec) as client:
            health_code, health_body = await _request_json(client, "GET", "/health")
            checks.append({
                "name": "health",
                "ok": health_code < 400,
                "status_code": health_code,
                "detail": _body_error(health_body),
            })

            hist_code, hist_body = await _request_json(client, "GET", "/api/simulation/history?limit=1")
            sim_id = None
            if hist_code < 400 and isinstance(hist_body, dict):
                items = hist_body.get("data") or []
                if items:
                    sim_id = items[0].get("simulation_id")

            checks.append({
                "name": "simulation_history",
                "ok": hist_code < 400 and bool(sim_id),
                "status_code": hist_code,
                "detail": f"simulation_id={sim_id}" if sim_id else _body_error(hist_body),
            })

            direct, direct_error = await _predict_via_direct_endpoint_verbose(client, {"ticker": ticker, "timeframe": "5m"})
            checks.append({
                "name": "predict_endpoint",
                "ok": bool(direct),
                "status_code": 200 if direct else 500,
                "detail": "direct /predict succeeded" if direct else (direct_error or "unknown"),
            })

            bridge, bridge_error = await _predict_via_oss_chat_bridge_verbose(
                client,
                {"ticker": ticker, "timeframe": "5m", "objective": "diagnostics check"},
            )
            checks.append({
                "name": "chat_bridge",
                "ok": bool(bridge),
                "status_code": 200 if bridge else 500,
                "detail": "chat bridge succeeded" if bridge else (bridge_error or "unknown"),
            })

            predict = await _predict_with_client(client, {"ticker": ticker, "timeframe": "5m"})
            provider_mode = predict.get("provider_mode", "unknown")
            verdict = "LIVE" if provider_mode.startswith("live") else "FALLBACK"

            ok_count = sum(1 for c in checks if c.get("ok"))
            readiness_score = int((ok_count / max(len(checks), 1)) * 100)

            recommendations: list[str] = []
            if not any(c.get("name") == "predict_endpoint" and c.get("ok") for c in checks):
                recommendations.append("Expose/enable a compatible POST /predict endpoint in MiroFish backend")
            if not any(c.get("name") == "chat_bridge" and c.get("ok") for c in checks):
                recommendations.append("Fix /api/report/chat runtime dependency (quota/key/provider) until 200 responses return")
            if not any(c.get("name") == "simulation_history" and c.get("ok") for c in checks):
                recommendations.append("Ensure /api/simulation/history returns at least one simulation_id")

            return {
                **base,
                "ticker": ticker,
                "verdict": verdict,
                "readiness_score": readiness_score,
                "can_use_live": verdict == "LIVE",
                "provider_mode": provider_mode,
                "live_error": predict.get("live_error"),
                "checks": checks,
                "recommendations": recommendations,
                "sample_predict": predict,
            }
    except Exception as e:
        return {
            **base,
            "ticker": ticker,
            "verdict": "ERROR",
            "readiness_score": 0,
            "can_use_live": False,
            "provider_mode": "fallback_stub",
            "live_error": str(e),
            "checks": checks,
            "recommendations": ["Inspect MiroFish connectivity and backend logs"],
        }
