"""security broker accounts and auth support tables

Revision ID: 0003_security_broker_accounts
Revises: 0002_hardening_constraints_idempotency
Create Date: 2026-03-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_security_broker_accounts"
down_revision: Union[str, Sequence[str], None] = "0002_hardening_constraints_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broker_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("account_ref", sa.String(length=128), nullable=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("credentials_fingerprint", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("provider", "environment", name="uq_broker_provider_env"),
    )
    op.create_index("ix_broker_provider", "broker_accounts", ["provider"], unique=False)
    op.create_index("ix_broker_environment", "broker_accounts", ["environment"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_broker_environment", table_name="broker_accounts")
    op.drop_index("ix_broker_provider", table_name="broker_accounts")
    op.drop_table("broker_accounts")
