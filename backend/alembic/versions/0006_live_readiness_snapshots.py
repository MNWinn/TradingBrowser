"""live readiness snapshots

Revision ID: 0006_live_readiness_snapshots
Revises: 0005_compliance_assignee
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_live_readiness_snapshots"
down_revision = "0005_compliance_assignee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_readiness_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("compliance_overdue_open", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mirofish", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_live_readiness_snapshot_created", "live_readiness_snapshots", ["created_at"])
    op.create_index("ix_live_readiness_snapshot_source_created", "live_readiness_snapshots", ["source", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_live_readiness_snapshot_source_created", table_name="live_readiness_snapshots")
    op.drop_index("ix_live_readiness_snapshot_created", table_name="live_readiness_snapshots")
    op.drop_table("live_readiness_snapshots")
