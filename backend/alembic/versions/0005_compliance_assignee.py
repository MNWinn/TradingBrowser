"""add assignee to compliance violations

Revision ID: 0005_compliance_assignee
Revises: 0004_compliance_violations
Create Date: 2026-03-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_compliance_assignee"
down_revision: Union[str, Sequence[str], None] = "0004_compliance_violations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("compliance_violations", sa.Column("assignee", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("compliance_violations", "assignee")
