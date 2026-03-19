from dataclasses import dataclass


@dataclass
class RiskState:
    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    concurrent_positions: int = 0
    kill_switch: bool = False


class RiskEngine:
    def __init__(self, policy: dict):
        self.policy = policy

    def hard_gate(self, order: dict, state: RiskState) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if state.kill_switch:
            reasons.append("KILL_SWITCH")
        if state.daily_loss >= self.policy.get("max_daily_loss", float("inf")):
            reasons.append("MAX_DAILY_LOSS")
        if state.weekly_loss >= self.policy.get("max_weekly_loss", float("inf")):
            reasons.append("MAX_WEEKLY_LOSS")
        if state.concurrent_positions >= self.policy.get("max_concurrent_positions", 999):
            reasons.append("MAX_CONCURRENT_POSITIONS")
        if order.get("notional", 0) > self.policy.get("max_capital_per_trade", float("inf")):
            reasons.append("MAX_CAPITAL_PER_TRADE")
        has_stop = bool(order.get("stop_loss"))
        if not has_stop:
            reasons.append("STOP_REQUIRED")
        return len(reasons) == 0, reasons

    def apply_soft_adjustments(self, signal: dict, adaptive_profile: dict) -> dict:
        adjusted = signal.copy()
        adjusted["position_size_suggestion"] = min(
            signal.get("position_size_suggestion", 0) * adaptive_profile.get("size_multiplier", 1.0),
            adaptive_profile.get("soft_size_cap", signal.get("position_size_suggestion", 0)),
        )
        adjusted["confidence"] = signal.get("confidence", 0) * adaptive_profile.get("confidence_multiplier", 1.0)
        return adjusted
