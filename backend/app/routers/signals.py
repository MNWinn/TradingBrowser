from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import SignalOutput
from app.services.audit import log_event
from app.services.policy import get_runtime_mode
from app.services.signal_engine import EnsembleSignalEngine

router = APIRouter(prefix="/signals", tags=["signals"])
engine = EnsembleSignalEngine()


@router.get("/{ticker}")
async def generate_signal(ticker: str, db: Session = Depends(get_db)):
    symbol = ticker.upper()
    mode, _ = get_runtime_mode(db)
    signal = await engine.generate(ticker=symbol, mode=mode)

    db.add(
        SignalOutput(
            ticker=symbol,
            action=signal["action"],
            confidence=signal["confidence"],
            consensus_score=signal["consensus_score"],
            disagreement_score=signal["disagreement_score"],
            reason_codes=signal["reason_codes"],
            explanation=signal["explanation"],
            execution_eligibility=signal["execution_eligibility"],
            model_version="v0.1-mvp",
        )
    )
    db.commit()
    log_event(db, "SIGNAL_GENERATED", {"ticker": symbol, "action": signal["action"], "mode": mode})
    return signal
