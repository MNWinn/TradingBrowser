from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import FeatureSnapshot
from app.services.audit import log_event

router = APIRouter(prefix="/chart", tags=["chart"])


@router.get("/probability/{ticker}")
def probability(ticker: str, timeframe: str = "5m", db: Session = Depends(get_db)):
    payload = {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "next_bar_direction_probability": {"up": 0.56, "down": 0.44},
        "target_before_stop_probability": 0.53,
        "expected_move_distribution": {"1": 0.3, "3": 0.8, "5": 1.2, "10": 2.0},
        "volatility_regime": "medium",
        "model_confidence": 0.61,
        "recommendation": "WATCHLIST",
        "contributors": ["probability_model", "technical_indicators", "mirofish"],
        "plain_english": "Slight bullish edge, but not enough for aggressive execution.",
    }

    db.add(
        FeatureSnapshot(
            ticker=ticker.upper(),
            ts=datetime.utcnow(),
            features=payload,
            regime=payload["volatility_regime"],
        )
    )
    db.commit()
    log_event(db, "CHART_PROBABILITY", {"ticker": ticker.upper(), "timeframe": timeframe})

    return payload
