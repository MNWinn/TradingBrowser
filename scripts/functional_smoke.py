#!/usr/bin/env python3
"""End-to-end functional smoke for TradingBrowser API.

Runs against local docker services by default:
- API: http://localhost:8000

Covers critical user-facing paths + edge cases.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("TB_API_BASE", "http://localhost:8000")
ADMIN = os.environ.get("ADMIN_API_TOKEN", "admin-dev-token")
TRADER = os.environ.get("TRADER_API_TOKEN", "trader-dev-token")
ANALYST = os.environ.get("ANALYST_API_TOKEN", "analyst-dev-token")


def req(method: str, path: str, payload: dict | None = None, token: str | None = None):
    url = f"{BASE}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as res:
            raw = res.read().decode("utf-8")
            ctype = (res.headers.get("Content-Type") or "").lower()
            if "application/json" in ctype:
                body = json.loads(raw) if raw else {}
            else:
                body = {"raw": raw}
            return res.status, body
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return e.code, body


def assert_ok(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    print(f"[smoke] base={BASE}")

    # root
    status, body = req("GET", "/")
    assert_ok(status == 200 and body.get("status") == "ok", "root failed")

    # market + chart
    status, quote = req("GET", "/market/quote/AAPL")
    assert_ok(status == 200 and quote.get("ticker") == "AAPL", "quote failed")

    status, bars = req("GET", "/market/bars/AAPL?timeframe=5m&limit=40")
    assert_ok(status == 200 and len(bars.get("bars", [])) >= 10, "bars failed")

    status, prob = req("GET", "/chart/probability/AAPL?timeframe=5m")
    assert_ok(status == 200 and prob.get("ticker") == "AAPL", "probability failed")

    # watchlist lifecycle
    user = "smoke-user"
    status, _ = req("POST", f"/watchlist/{user}/AAPL")
    assert_ok(status == 200, "watchlist add AAPL failed")
    status, _ = req("POST", f"/watchlist/{user}/MSFT")
    assert_ok(status == 200, "watchlist add MSFT failed")

    status, wl = req("GET", f"/watchlist/{user}")
    assert_ok(status == 200 and "AAPL" in wl.get("items", []), "watchlist get failed")

    status, _ = req("DELETE", f"/watchlist/{user}/MSFT")
    assert_ok(status == 200, "watchlist remove failed")

    # signals + swarm
    status, sig = req("GET", "/signals/AAPL")
    assert_ok(status == 200 and sig.get("ticker") == "AAPL", "signal failed")

    status, swarm = req("POST", "/swarm/run/AAPL")
    assert_ok(status == 200 and swarm.get("task_id"), "swarm run failed")
    task_id = swarm["task_id"]

    status, st = req("GET", f"/swarm/status/{urllib.parse.quote(task_id)}")
    assert_ok(status == 200 and st.get("status") in {"completed", "not_found"}, "swarm status failed")

    status, results = req("GET", "/swarm/results/AAPL")
    assert_ok(status == 200 and isinstance(results.get("results", []), list), "swarm results failed")

    # mode control + execution edge cases
    status, mode = req("GET", "/execution/mode")
    assert_ok(status == 200 and mode.get("mode") in {"research", "paper", "live"}, "get mode failed")

    status, history_before = req("GET", "/execution/readiness-history?limit=200", token=ANALYST)
    assert_ok(status == 200 and isinstance(history_before.get("snapshots", []), list), "readiness history precheck failed")
    before_count = len(history_before.get("snapshots", []))

    status, readiness = req("GET", "/execution/live-readiness", token=ANALYST)
    assert_ok(status == 200 and "ready" in readiness and "checks" in readiness, "live readiness failed")

    status, history_after_readiness = req("GET", "/execution/readiness-history?limit=200", token=ANALYST)
    assert_ok(status == 200, "readiness history after readiness call failed")
    assert_ok(
        len(history_after_readiness.get("snapshots", [])) >= before_count + 1,
        "readiness history did not grow after live-readiness",
    )

    # Invalid token edge
    status, _ = req("PUT", "/execution/mode", {"mode": "paper", "live_trading_enabled": False}, token="bad-token")
    assert_ok(status == 401, "invalid token should fail")

    status, _ = req(
        "PUT",
        "/execution/mode",
        {"mode": "paper", "live_trading_enabled": False, "changed_by": "smoke"},
        token=ADMIN,
    )
    assert_ok(status == 200, "set paper mode failed")

    status, _ = req(
        "PUT",
        "/execution/mode",
        {
            "mode": "live",
            "live_trading_enabled": True,
            "changed_by": "smoke-trend",
            "confirmation": "ENABLE_LIVE_TRADING",
            "force_enable_live": True,
        },
        token=ADMIN,
    )
    assert_ok(status == 200, "force enable live for trend snapshot failed")

    status, history_after_live_update = req("GET", "/execution/readiness-history?limit=200", token=ANALYST)
    assert_ok(status == 200 and history_after_live_update.get("latest"), "readiness history after live update failed")

    status, readiness_summary = req("GET", "/execution/live-readiness/summary?limit=200", token=ANALYST)
    assert_ok(status == 200 and "total" in readiness_summary and "pass_rate" in readiness_summary, "readiness summary failed")
    snapshots = history_after_live_update.get("snapshots", [])
    assert_ok(len(snapshots) >= before_count + 2, "readiness history did not capture live mode update snapshot")
    assert_ok(any(s.get("source") == "live_mode_update" for s in snapshots), "missing live_mode_update snapshot")
    assert_ok(history_after_live_update["latest"].get("readiness"), "latest snapshot missing readiness payload")

    status, bad_validate = req("POST", "/execution/validate", {"symbol": "AAPL", "side": "buy"})
    assert_ok(status == 422, "validate missing qty/notional edge failed")

    payload = {
        "symbol": "AAPL",
        "side": "buy",
        "qty": 1,
        "type": "market",
        "stop_loss": 1,
        "recommendation": {"action": "LONG"},
        "rationale": {"source": "smoke"},
        "idempotency_key": "smoke-order-1",
    }
    status, val = req("POST", "/execution/validate", payload)
    assert_ok(status == 200 and "hard_ok" in val, "validate order failed")

    status, order = req("POST", "/execution/order", payload, token=TRADER)
    assert_ok(status == 200 and (order.get("status") == "mock" or order.get("journal_id")), "submit order failed")

    # Idempotent replay
    status, replay = req("POST", "/execution/order", payload, token=TRADER)
    assert_ok(status == 200 and replay.get("idempotent_replay") is True, "idempotent replay failed")

    # Journal update
    status, journal = req("GET", "/journal?limit=5")
    assert_ok(status == 200 and isinstance(journal.get("items", []), list), "journal list failed")
    if journal.get("items"):
        entry_id = journal["items"][0]["id"]
        status, _ = req(
            "PATCH",
            f"/journal/{entry_id}/outcome",
            {"state": "closed", "fill_price": 100, "fill_qty": 1, "pnl": 0},
            token=TRADER,
        )
        assert_ok(status == 200, "journal outcome update failed")

    # Compliance lifecycle
    status, comp = req(
        "POST",
        "/compliance/violations",
        {
            "policy_name": "pre_trade_controls",
            "rule_code": "SMOKE_RULE",
            "severity": "medium",
            "symbol": "AAPL",
            "assignee": "compliance-console",
            "details": {"source": "smoke"},
        },
        token=TRADER,
    )
    assert_ok(status == 200 and comp.get("id"), "compliance create failed")
    violation_id = comp["id"]

    status, _ = req("PATCH", f"/compliance/violations/{violation_id}", {"status": "acknowledged", "assignee": "qa-user"}, token=TRADER)
    assert_ok(status == 200, "compliance update failed")

    status, lst = req("GET", "/compliance/violations?assignee=qa-user&limit=20", token=ANALYST)
    assert_ok(status == 200 and isinstance(lst.get("items", []), list), "compliance list with assignee failed")

    status, _ = req("PATCH", "/compliance/violations-bulk", {"ids": [violation_id], "status": "remediated"}, token=TRADER)
    assert_ok(status == 200, "compliance bulk failed")

    status, tl = req("GET", f"/compliance/violations/{violation_id}/timeline?limit=20", token=ANALYST)
    assert_ok(status == 200 and isinstance(tl.get("items", []), list), "compliance timeline failed")

    status, summary = req("GET", "/compliance/summary", token=ANALYST)
    assert_ok(status == 200 and "open" in summary, "compliance summary failed")

    status, analytics = req("GET", "/compliance/analytics", token=ANALYST)
    assert_ok(status == 200 and "mttr_hours" in analytics, "compliance analytics failed")

    status, _ = req("GET", "/compliance/violations/export.csv?sort=severity", token=ANALYST)
    assert_ok(status == 200, "compliance export failed")

    # Mirofish functional checks (stub or live)
    status, mstat = req("GET", "/mirofish/status")
    assert_ok(status == 200 and mstat.get("provider") == "mirofish", "mirofish status failed")

    status, mpred = req("POST", "/mirofish/predict", {"ticker": "AAPL", "timeframe": "5m"})
    assert_ok(status == 200 and mpred.get("provider") == "mirofish" and mpred.get("directional_bias"), "mirofish predict failed")

    status, mdeep = req("POST", "/mirofish/deep-swarm", {"ticker": "AAPL"})
    assert_ok(status == 200 and mdeep.get("provider") == "mirofish", "mirofish deep-swarm failed")

    status, mdiag = req("POST", "/mirofish/diagnostics", {"ticker": "AAPL"})
    assert_ok(status == 200 and mdiag.get("verdict") in {"LIVE", "FALLBACK", "ERROR", "NOT_CONFIGURED"}, "mirofish diagnostics failed")

    # Settings broker accounts (if encryption key configured)
    status, up = req(
        "POST",
        "/settings/broker-accounts",
        {
            "provider": "alpaca",
            "environment": "paper",
            "account_ref": "smoke-account",
            "credentials": {"api_key": "k", "api_secret": "s"},
        },
        token=ADMIN,
    )
    if status == 200:
        status, _ = req("GET", "/settings/broker-accounts", token=TRADER)
        assert_ok(status == 200, "broker account list failed")
    else:
        # Acceptable in dev if ENCRYPTION_KEY missing
        assert_ok(status in {400, 500}, "unexpected broker account upsert status")

    # risk / audit / evaluation / strategy endpoints
    status, _ = req("GET", "/risk/profile")
    assert_ok(status == 200, "risk profile failed")

    status, _ = req("GET", "/risk/policy")
    assert_ok(status == 200, "risk policy get failed")

    status, _ = req("PUT", "/risk/policy", {"hard_constraints": {"max_daily_loss": 500}}, token=ADMIN)
    assert_ok(status == 200, "risk policy update failed")

    status, _ = req("POST", "/evaluation/daily")
    assert_ok(status == 200, "evaluation daily failed")

    status, _ = req("POST", "/strategies/backtest", {"name": "smoke-strat", "ticker": "AAPL", "timeframe": "5m"})
    assert_ok(status == 200, "strategy backtest failed")

    # Training endpoint may require broker/worker; verify responds but tolerate infra issue
    status, _ = req("POST", "/training/run", token=ADMIN)
    assert_ok(status in {200, 500, 503}, "training run unexpected status")

    status, logs = req("GET", "/audit/logs?limit=20")
    assert_ok(status == 200 and isinstance(logs.get("items", []), list), "audit logs failed")

    print("[smoke] PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[smoke] FAIL: {e}")
        sys.exit(1)
