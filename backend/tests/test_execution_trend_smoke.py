from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
ANALYST_HEADERS = {"Authorization": "Bearer analyst-dev-token"}
ADMIN_HEADERS = {"Authorization": "Bearer admin-dev-token"}


def _trend(limit: int = 100):
    return client.get(f"/execution/readiness-history?limit={limit}", headers=ANALYST_HEADERS)


def test_readiness_history_grows_after_readiness_calls_and_live_mode_attempt():
    before_resp = _trend()
    assert before_resp.status_code == 200
    before = before_resp.json()
    before_count = len(before.get("snapshots", []))

    r1 = client.get("/execution/live-readiness", headers=ANALYST_HEADERS)
    assert r1.status_code == 200
    first = r1.json()

    r2 = client.get("/execution/live-readiness", headers=ANALYST_HEADERS)
    assert r2.status_code == 200

    update = client.put(
        "/execution/mode",
        headers=ADMIN_HEADERS,
        json={
            "mode": "live",
            "live_trading_enabled": True,
            "changed_by": "trend-smoke",
            "confirmation": "ENABLE_LIVE_TRADING",
            "force_enable_live": True,
        },
    )
    assert update.status_code == 200

    after_resp = _trend()
    assert after_resp.status_code == 200
    after = after_resp.json()

    snapshots = after.get("snapshots", [])
    assert len(snapshots) >= before_count + 3
    assert after.get("latest")
    assert after["latest"]["readiness"]["ready"] == snapshots[0]["readiness"]["ready"]

    live_mode_entries = [s for s in snapshots if s.get("source") == "live_mode_update"]
    assert live_mode_entries, "expected at least one snapshot from live mode update"

    latest_readiness = first.get("ready")
    assert any(s.get("readiness", {}).get("ready") == latest_readiness for s in snapshots)

    summary = client.get("/execution/live-readiness/summary?limit=200", headers=ANALYST_HEADERS)
    assert summary.status_code == 200
    s = summary.json()
    assert "total" in s and "pass_count" in s and "fail_count" in s and "pass_rate" in s
