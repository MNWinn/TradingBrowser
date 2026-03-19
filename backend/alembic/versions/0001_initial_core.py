"""initial core tables

Revision ID: 0001_initial_core
Revises: None
Create Date: 2026-03-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_core"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "signal_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("consensus_score", sa.Float(), nullable=False),
        sa.Column("disagreement_score", sa.Float(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("execution_eligibility", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "swarm_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "swarm_agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=False),
    )

    op.create_table(
        "swarm_consensus_outputs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("aggregated_recommendation", sa.String(length=16), nullable=True),
        sa.Column("consensus_score", sa.Float(), nullable=True),
        sa.Column("disagreement_score", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broker_order_id", sa.String(length=128), nullable=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("qty", sa.Float(), nullable=True),
        sa.Column("order_type", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("rationale", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "risk_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("hard_constraints", sa.JSON(), nullable=False),
        sa.Column("soft_constraints", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "execution_modes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("changed_by", sa.String(length=64), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("recommendation", sa.JSON(), nullable=True),
        sa.Column("execution", sa.JSON(), nullable=True),
        sa.Column("outcome", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "daily_model_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eval_date", sa.Date(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "agent_performance_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("setup_type", sa.String(length=64), nullable=True),
        sa.Column("regime", sa.String(length=32), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("agent_performance_stats")
    op.drop_table("daily_model_evaluations")
    op.drop_table("trade_journal")
    op.drop_table("execution_modes")
    op.drop_table("risk_policies")
    op.drop_table("paper_orders")
    op.drop_table("swarm_consensus_outputs")
    op.drop_table("swarm_agent_runs")
    op.drop_table("swarm_tasks")
    op.drop_table("signal_outputs")
    op.drop_table("feature_snapshots")
    op.drop_table("watchlists")
