"""
Database models for MiroFish prediction tracking and analytics.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MiroFishPrediction(Base):
    """
    Stores every MiroFish prediction with timestamp and metadata.
    """
    __tablename__ = "mirofish_predictions"
    __table_args__ = (
        Index("ix_mirofish_predictions_ticker_predicted", "ticker", "predicted_at"),
        Index("ix_mirofish_predictions_timeframe", "timeframe", "predicted_at"),
        Index("ix_mirofish_predictions_signal_type", "signal_type", "predicted_at"),
        Index("ix_mirofish_predictions_outcome", "outcome_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    signal_type: Mapped[str] = mapped_column(String(16), index=True)  # LONG, SHORT, NEUTRAL, etc.
    confidence: Mapped[float] = mapped_column(Float)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)  # 5m, 1h, 1d, etc.
    lens: Mapped[str] = mapped_column(String(32), default="overall")  # trend, momentum, catalyst, etc.
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    price_at_prediction: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Timestamps
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Outcome reference
    outcome_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("mirofish_prediction_outcomes.id"), nullable=True)
    outcome: Mapped["PredictionOutcome"] = relationship("PredictionOutcome", back_populates="prediction", uselist=False)


class PredictionOutcome(Base):
    """
    Tracks the outcome of a MiroFish prediction.
    """
    __tablename__ = "mirofish_prediction_outcomes"
    __table_args__ = (
        Index("ix_mirofish_outcomes_was_correct", "was_correct", "outcome_time"),
        Index("ix_mirofish_outcomes_actual_return", "actual_return", "outcome_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(Integer, ForeignKey("mirofish_predictions.id"))
    
    # Outcome data
    actual_return: Mapped[float] = mapped_column(Float)  # Actual return achieved
    outcome_price: Mapped[float] = mapped_column(Float)
    outcome_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    was_correct: Mapped[bool] = mapped_column(Boolean, index=True)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Relationship
    prediction: Mapped[MiroFishPrediction] = relationship("MiroFishPrediction", back_populates="outcome")


class MiroFishAccuracySummary(Base):
    """
    Pre-computed accuracy summaries for fast lookups.
    """
    __tablename__ = "mirofish_accuracy_summaries"
    __table_args__ = (
        UniqueConstraint("ticker", "timeframe", "signal_type", name="uq_mirofish_accuracy_summary"),
        Index("ix_mirofish_accuracy_ticker_tf", "ticker", "timeframe"),
        Index("ix_mirofish_accuracy_signal_type", "signal_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    signal_type: Mapped[str] = mapped_column(String(16), index=True)
    
    # Stats
    total_predictions: Mapped[int] = mapped_column(Integer, default=0)
    correct_predictions: Mapped[int] = mapped_column(Integer, default=0)
    accuracy_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
