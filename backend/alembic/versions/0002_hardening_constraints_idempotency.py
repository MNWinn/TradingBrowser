"""hardening constraints, indexes, idempotency table

Revision ID: 0002_hardening_constraints_idempotency
Revises: 0001_initial_core
Create Date: 2026-03-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_hardening_constraints_idempotency"
down_revision: Union[str, Sequence[str], None] = "0001_initial_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_signal_ticker_created", "signal_outputs", ["ticker", "created_at"], unique=False)
    op.create_index("ix_trade_journal_ticker_created", "trade_journal", ["ticker", "created_at"], unique=False)
    op.create_index("ix_feature_ticker_ts", "feature_snapshots", ["ticker", "ts"], unique=False)
    op.create_index("ix_execution_mode_changed_at", "execution_modes", ["changed_at"], unique=False)
    op.create_index("ix_watchlist_user_position", "watchlists", ["user_id", "position"], unique=False)

    op.create_unique_constraint("uq_watchlist_user_ticker", "watchlists", ["user_id", "ticker"])
    op.create_unique_constraint("uq_agent_setup_regime", "agent_performance_stats", ["agent_name", "setup_type", "regime"])
    op.create_unique_constraint("uq_paper_orders_broker_order_id", "paper_orders", ["broker_order_id"])

    op.create_table(
        "execution_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("endpoint", "idempotency_key", name="uq_execution_request_key"),
    )
    op.create_index("ix_execution_requests_endpoint", "execution_requests", ["endpoint"], unique=False)
    op.create_index("ix_execution_requests_key", "execution_requests", ["idempotency_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_execution_requests_key", table_name="execution_requests")
    op.drop_index("ix_execution_requests_endpoint", table_name="execution_requests")
    op.drop_table("execution_requests")

    op.drop_constraint("uq_paper_orders_broker_order_id", "paper_orders", type_="unique")
    op.drop_constraint("uq_agent_setup_regime", "agent_performance_stats", type_="unique")
    op.drop_constraint("uq_watchlist_user_ticker", "watchlists", type_="unique")

    op.drop_index("ix_watchlist_user_position", table_name="watchlists")
    op.drop_index("ix_execution_mode_changed_at", table_name="execution_modes")
    op.drop_index("ix_feature_ticker_ts", table_name="feature_snapshots")
    op.drop_index("ix_trade_journal_ticker_created", table_name="trade_journal")
    op.drop_index("ix_signal_ticker_created", table_name="signal_outputs")
