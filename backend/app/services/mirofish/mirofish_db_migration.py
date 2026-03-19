"""
Database migration script for MiroFish Deep Dive features.

Run this script to create the necessary database tables for:
- mirofish_explainer.py: MiroFishExplanation, MiroFishExplanationHistory
- mirofish_scenarios.py: MiroFishScenario
- mirofish_backtest.py: MiroFishBacktest, MiroFishBacktestConfig
- mirofish_comparison.py: MiroFishComparison, MiroFishAccuracyTracking
"""

from sqlalchemy import create_engine, Column, String, Float, DateTime, JSON, Integer, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()


class MiroFishExplanation(Base):
    """Database model for storing prediction explanations."""
    __tablename__ = "mirofish_explanations"
    
    id = Column(String(36), primary_key=True)
    prediction_id = Column(String(36), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Overall prediction
    overall_bias = Column(String(20), nullable=False)
    overall_confidence = Column(Float, nullable=False)
    
    # Component breakdown (stored as JSON)
    components = Column(JSON, default=dict)
    factor_weights = Column(JSON, default=dict)
    key_drivers = Column(JSON, default=list)
    confidence_breakdown = Column(JSON, default=dict)
    contradicting_signals = Column(JSON, default=list)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    lens = Column(String(50), nullable=True)
    prediction_metadata = Column(JSON, default=dict)


class MiroFishExplanationHistory(Base):
    """Database model for tracking explanation history."""
    __tablename__ = "mirofish_explanation_history"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Historical tracking
    prediction_id = Column(String(36), nullable=False)
    explanation_id = Column(String(36), nullable=False)
    accuracy = Column(Float, nullable=True)  # Actual outcome accuracy
    pnl_outcome = Column(Float, nullable=True)  # Actual P&L


class MiroFishScenario(Base):
    """Database model for storing scenario analyses."""
    __tablename__ = "mirofish_scenarios"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Scenario parameters
    current_price = Column(Float, nullable=False)
    scenario_type = Column(String(50), nullable=False)  # what_if, best_case, worst_case, etc.
    
    # Results
    target_price = Column(Float, nullable=True)
    price_change_pct = Column(Float, nullable=True)
    probability = Column(Float, nullable=True)
    
    # Detailed results
    outcomes = Column(JSON, default=list)
    risk_reward = Column(JSON, default=dict)
    probability_distribution = Column(JSON, default=dict)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    prediction_metadata = Column(JSON, default=dict)


class MiroFishBacktest(Base):
    """Database model for storing backtest results."""
    __tablename__ = "mirofish_backtests"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Backtest parameters
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    timeframe = Column(String(10), nullable=False)
    initial_capital = Column(Float, default=100000.0)
    
    # Results summary
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Performance metrics
    total_return = Column(Float, default=0.0)
    total_return_pct = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)
    
    # Detailed results
    trades = Column(JSON, default=list)
    equity_curve = Column(JSON, default=list)
    monthly_returns = Column(JSON, default=dict)
    
    # Configuration
    config = Column(JSON, default=dict)
    prediction_metadata = Column(JSON, default=dict)


class MiroFishBacktestConfig(Base):
    """Database model for storing backtest configurations."""
    __tablename__ = "mirofish_backtest_configs"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(500), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Configuration parameters
    entry_threshold = Column(Float, default=0.6)  # Min confidence to enter
    exit_threshold = Column(Float, default=0.3)  # Max confidence to hold
    stop_loss_pct = Column(Float, default=0.05)  # Stop loss percentage
    take_profit_pct = Column(Float, default=0.10)  # Take profit percentage
    max_position_size = Column(Float, default=0.2)  # Max % of capital per trade
    max_holding_days = Column(Integer, default=5)
    
    # Signal configuration
    use_deep_swarm = Column(Boolean, default=False)
    timeframes = Column(JSON, default=list)
    lenses = Column(JSON, default=list)
    
    prediction_metadata = Column(JSON, default=dict)


class MiroFishComparison(Base):
    """Database model for storing signal comparisons."""
    __tablename__ = "mirofish_comparisons"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Signals compared
    mirofish_bias = Column(String(20), nullable=False)
    mirofish_confidence = Column(Float, nullable=False)
    
    technical_bias = Column(String(20), nullable=True)
    technical_confidence = Column(Float, nullable=True)
    
    market_regime = Column(String(50), nullable=True)
    sentiment_bias = Column(String(20), nullable=True)
    
    # Agreement metrics
    agreement_score = Column(Float, nullable=False)
    disagreement_count = Column(Integer, default=0)
    
    # Detailed comparison
    comparison_data = Column(JSON, default=dict)
    accuracy_tracking = Column(JSON, default=dict)
    
    # Metadata
    timeframe = Column(String(10), nullable=True)
    prediction_metadata = Column(JSON, default=dict)


class MiroFishAccuracyTracking(Base):
    """Database model for tracking signal accuracy over time."""
    __tablename__ = "mirofish_accuracy_tracking"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Signal source
    source = Column(String(50), nullable=False)  # mirofish, technical, combined, etc.
    
    # Prediction
    predicted_bias = Column(String(20), nullable=False)
    predicted_confidence = Column(Float, nullable=False)
    
    # Outcome (filled in later)
    actual_return = Column(Float, nullable=True)
    actual_direction = Column(String(20), nullable=True)  # UP, DOWN, FLAT
    was_correct = Column(Boolean, nullable=True)
    
    # Performance metrics
    pnl_potential = Column(Float, nullable=True)  # What would have been made
    holding_days = Column(Integer, nullable=True)
    
    # Resolution
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_price = Column(Float, nullable=True)


def create_tables(database_url: str | None = None):
    """Create all MiroFish Deep Dive tables."""
    from app.core.config import settings
    
    url = database_url or settings.database_url
    engine = create_engine(url, pool_pre_ping=True)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    print("✅ MiroFish Deep Dive tables created successfully:")
    print("  - mirofish_explanations")
    print("  - mirofish_explanation_history")
    print("  - mirofish_scenarios")
    print("  - mirofish_backtests")
    print("  - mirofish_backtest_configs")
    print("  - mirofish_comparisons")
    print("  - mirofish_accuracy_tracking")


def drop_tables(database_url: str | None = None):
    """Drop all MiroFish Deep Dive tables (use with caution!)."""
    from app.core.config import settings
    
    url = database_url or settings.database_url
    engine = create_engine(url, pool_pre_ping=True)
    
    # Drop all tables
    Base.metadata.drop_all(engine)
    
    print("⚠️ MiroFish Deep Dive tables dropped:")
    print("  - mirofish_explanations")
    print("  - mirofish_explanation_history")
    print("  - mirofish_scenarios")
    print("  - mirofish_backtests")
    print("  - mirofish_backtest_configs")
    print("  - mirofish_comparisons")
    print("  - mirofish_accuracy_tracking")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        drop_tables()
    else:
        create_tables()
