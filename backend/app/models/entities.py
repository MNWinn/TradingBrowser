from datetime import datetime, date
from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    JSON,
    Text,
    Date,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
        Index("ix_watchlist_user_position", "user_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    __table_args__ = (Index("ix_feature_ticker_ts", "ticker", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    features: Mapped[dict] = mapped_column(JSON)
    regime: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SignalOutput(Base):
    __tablename__ = "signal_outputs"
    __table_args__ = (Index("ix_signal_ticker_created", "ticker", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    action: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    consensus_score: Mapped[float] = mapped_column(Float)
    disagreement_score: Mapped[float] = mapped_column(Float)
    reason_codes: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    execution_eligibility: Mapped[dict] = mapped_column(JSON)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SwarmTask(Base):
    __tablename__ = "swarm_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="completed")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SwarmAgentRun(Base):
    __tablename__ = "swarm_agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    recommendation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output: Mapped[dict] = mapped_column(JSON)


class SwarmConsensusOutput(Base):
    __tablename__ = "swarm_consensus_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(128), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    aggregated_recommendation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    consensus_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    disagreement_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticePortfolio(Base):
    """Virtual portfolio for paper trading."""
    __tablename__ = "practice_portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_practice_portfolio_user"),
        Index("ix_practice_portfolio_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    initial_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    total_equity: Mapped[float] = mapped_column(Float, default=100000.0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_percent: Mapped[float] = mapped_column(Float, default=0.0)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticePosition(Base):
    """Virtual position in paper trading."""
    __tablename__ = "practice_positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", name="uq_practice_position_portfolio_ticker"),
        Index("ix_practice_position_portfolio", "portfolio_id"),
        Index("ix_practice_position_ticker", "ticker"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(Integer, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8), default="long")  # long, short
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticeTrade(Base):
    """Paper trade execution record."""
    __tablename__ = "practice_trades"
    __table_args__ = (
        Index("ix_practice_trade_user", "user_id"),
        Index("ix_practice_trade_ticker", "ticker"),
        Index("ix_practice_trade_strategy", "strategy_id"),
        Index("ix_practice_trade_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))  # buy, sell
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="filled")  # pending, filled, partial, cancelled, rejected
    strategy_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    rationale: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PracticePerformance(Base):
    """Practice trading performance metrics."""
    __tablename__ = "practice_performance"
    __table_args__ = (
        Index("ix_practice_perf_user", "user_id"),
        Index("ix_practice_perf_strategy", "strategy_id"),
        Index("ix_practice_perf_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    strategy_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PracticeChallenge(Base):
    """Trading challenge for practice mode."""
    __tablename__ = "practice_challenges"
    __table_args__ = (
        Index("ix_practice_challenge_user", "user_id"),
        Index("ix_practice_challenge_status", "status"),
        Index("ix_practice_challenge_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    challenge_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    challenge_type: Mapped[str] = mapped_column(String(32))  # daily, risk_management, consistency, profit_target, skill_based
    criteria: Mapped[dict] = mapped_column(JSON)
    reward_points: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active, completed, failed, expired
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PracticeAchievement(Base):
    """Achievement earned in practice trading."""
    __tablename__ = "practice_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_practice_achievement_user_id"),
        Index("ix_practice_achievement_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    achievement_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(String(16))  # bronze, silver, gold, platinum, diamond
    icon: Mapped[str] = mapped_column(String(8), default="🏆")
    criteria_met: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PracticeUserStats(Base):
    """Aggregated user statistics for practice trading."""
    __tablename__ = "practice_user_stats"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_practice_user_stats_user"),
        Index("ix_practice_user_stats_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_challenges_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_achievements_earned: Mapped[int] = mapped_column(Integer, default=0)
    current_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    favorite_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rationale: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    __table_args__ = (UniqueConstraint("provider", "environment", name="uq_broker_provider_env"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    environment: Mapped[str] = mapped_column(String(16), index=True)
    account_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    credentials_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskPolicy(Base):
    __tablename__ = "risk_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_name: Mapped[str] = mapped_column(String(64), unique=True)
    hard_constraints: Mapped[dict] = mapped_column(JSON)
    soft_constraints: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExecutionMode(Base):
    __tablename__ = "execution_modes"
    __table_args__ = (Index("ix_execution_mode_changed_at", "changed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), default="research")
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    changed_by: Mapped[str] = mapped_column(String(64), default="system")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExecutionRequest(Base):
    __tablename__ = "execution_requests"
    __table_args__ = (UniqueConstraint("endpoint", "idempotency_key", name="uq_execution_request_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    response_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TradeJournal(Base):
    __tablename__ = "trade_journal"
    __table_args__ = (Index("ix_trade_journal_ticker_created", "ticker", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    mode: Mapped[str] = mapped_column(String(16))
    recommendation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyModelEvaluation(Base):
    __tablename__ = "daily_model_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_date: Mapped[date] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentPerformanceStat(Base):
    __tablename__ = "agent_performance_stats"
    __table_args__ = (
        UniqueConstraint("agent_name", "setup_type", "regime", name="uq_agent_setup_regime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    setup_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ComplianceViolation(Base):
    __tablename__ = "compliance_violations"
    __table_args__ = (
        Index("ix_compliance_status_created", "status", "created_at"),
        Index("ix_compliance_symbol_created", "symbol", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(64), index=True)
    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="open")
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LiveReadinessSnapshot(Base):
    __tablename__ = "live_readiness_snapshots"
    __table_args__ = (
        Index("ix_live_readiness_snapshot_created", "created_at"),
        Index("ix_live_readiness_snapshot_source_created", "source", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    compliance_overdue_open: Mapped[int] = mapped_column(Integer, default=0)
    mirofish: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentInstance(Base):
    __tablename__ = "agent_instances"
    __table_args__ = (
        Index("ix_agent_instances_status_created", "status", "created_at"),
        Index("ix_agent_instances_ticker_status", "ticker", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    instance_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_output: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentLog(Base):
    __tablename__ = "agent_logs"
    __table_args__ = (
        Index("ix_agent_logs_instance_created", "instance_id", "created_at"),
        Index("ix_agent_logs_level_created", "level", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
