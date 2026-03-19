"""compliance violations queue

Revision ID: 0004_compliance_violations
Revises: 0003_security_broker_accounts
Create Date: 2026-03-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_compliance_violations"
down_revision: Union[str, Sequence[str], None] = "0003_security_broker_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_violations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy_name", sa.String(length=64), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_compliance_policy", "compliance_violations", ["policy_name"], unique=False)
    op.create_index("ix_compliance_rule", "compliance_violations", ["rule_code"], unique=False)
    op.create_index("ix_compliance_symbol", "compliance_violations", ["symbol"], unique=False)
    op.create_index("ix_compliance_status_created", "compliance_violations", ["status", "created_at"], unique=False)
    op.create_index("ix_compliance_symbol_created", "compliance_violations", ["symbol", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_compliance_symbol_created", table_name="compliance_violations")
    op.drop_index("ix_compliance_status_created", table_name="compliance_violations")
    op.drop_index("ix_compliance_symbol", table_name="compliance_violations")
    op.drop_index("ix_compliance_rule", table_name="compliance_violations")
    op.drop_index("ix_compliance_policy", table_name="compliance_violations")
    op.drop_table("compliance_violations")
