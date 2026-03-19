from fastapi import APIRouter

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("/backtest")
def backtest(payload: dict):
    return {
        "strategy": payload.get("name", "Unnamed"),
        "equity_curve": [100000, 100300, 100150, 100600],
        "win_rate": 0.54,
        "drawdown": 0.07,
        "expectancy": 0.18,
    }
