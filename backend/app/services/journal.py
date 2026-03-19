from datetime import datetime


def build_outcome(payload: dict) -> dict:
    return {
        "state": payload.get("state", "filled"),
        "fill_price": payload.get("fill_price"),
        "fill_qty": payload.get("fill_qty"),
        "pnl": payload.get("pnl"),
        "notes": payload.get("notes"),
        "updated_at": datetime.utcnow().isoformat(),
    }


def merge_state(tags: dict | None, state: str) -> dict:
    out = tags.copy() if tags else {}
    out["state"] = state
    out["updated_at"] = datetime.utcnow().isoformat()
    return out
