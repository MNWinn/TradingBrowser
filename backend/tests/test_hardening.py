import pytest

from app.schemas.execution import OrderRequest
from app.services.journal import build_outcome, merge_state
from app.services.policy import validate_mode_transition
from app.services.risk import RiskEngine, RiskState


def test_mode_gating_live_requires_confirmation_token():
    with pytest.raises(ValueError):
        validate_mode_transition(mode="live", live_enabled=True, confirmation=None)

    validate_mode_transition(mode="live", live_enabled=True, confirmation="ENABLE_LIVE_TRADING")


def test_risk_engine_blocks_order_without_stop_and_over_cap():
    engine = RiskEngine(
        {
            "max_capital_per_trade": 1000,
            "max_daily_loss": 500,
            "max_weekly_loss": 1000,
            "max_concurrent_positions": 3,
        }
    )
    ok, reasons = engine.hard_gate({"notional": 2000}, RiskState())
    assert not ok
    assert "MAX_CAPITAL_PER_TRADE" in reasons
    assert "STOP_REQUIRED" in reasons


def test_journal_outcome_helpers_update_state():
    payload = {"state": "filled", "fill_price": 101.5, "fill_qty": 10, "pnl": 4.2}
    outcome = build_outcome(payload)
    tags = merge_state({"state": "submitted"}, outcome["state"])

    assert outcome["state"] == "filled"
    assert outcome["fill_price"] == 101.5
    assert tags["state"] == "filled"
    assert "updated_at" in tags


def test_order_schema_requires_qty_or_notional():
    with pytest.raises(Exception):
        OrderRequest(symbol="AAPL", side="buy")

    obj = OrderRequest(symbol="AAPL", side="buy", qty=1)
    assert obj.qty == 1
