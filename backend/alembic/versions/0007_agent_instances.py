"""agent instances and logs

Revision ID: 0007_agent_instances
Revises: 0006_live_readiness_snapshots
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0007_agent_instances"
down_revision = "0006_live_readiness_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_instances table
    op.create_table(
        "agent_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_name", sa.String(length=64), nullable=False, index=True),
        sa.Column("instance_id", sa.String(length=128), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("task_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("ticker", sa.String(length=16), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("health_score", sa.Float(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_output", sa.Text(), nullable=True),
    )
    
    # Create indexes for agent_instances
    op.create_index("ix_agent_instances_status_created", "agent_instances", ["status", "created_at"])
    op.create_index("ix_agent_instances_ticker_status", "agent_instances", ["ticker", "status"])
    op.create_index("ix_agent_instances_task_id", "agent_instances", ["task_id"])
    
    # Create agent_logs table
    op.create_table(
        "agent_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instance_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    
    # Create indexes for agent_logs
    op.create_index("ix_agent_logs_instance_created", "agent_logs", ["instance_id", "created_at"])
    op.create_index("ix_agent_logs_level_created", "agent_logs", ["level", "created_at"])


def downgrade() -> None:
    # Drop agent_logs indexes and table
    op.drop_index("ix_agent_logs_level_created", table_name="agent_logs")
    op.drop_index("ix_agent_logs_instance_created", table_name="agent_logs")
    op.drop_table("agent_logs")
    
    # Drop agent_instances indexes and table
    op.drop_index("ix_agent_instances_task_id", table_name="agent_instances")
    op.drop_index("ix_agent_instances_ticker_status", table_name="agent_instances")
    op.drop_index("ix_agent_instances_status_created", table_name="agent_instances")
    op.drop_table("agent_instances")
