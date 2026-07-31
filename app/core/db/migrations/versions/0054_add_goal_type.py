"""add goal_type to goals (수치형/횟수형 목표 구분)

Revision ID: 0054
Revises: 0053
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("goal_type", sa.String(length=10), nullable=False, server_default="NUMERIC"),
    )


def downgrade() -> None:
    op.drop_column("goals", "goal_type")
