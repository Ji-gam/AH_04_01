"""add goals table (F-GOAL-1 목표 CRUD + F-GOAL-2 AI 가이드)

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("start_value", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("target_value", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("current_value", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_achieved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("guide_content", sa.Text(), nullable=True),
        sa.Column("guide_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_goals_profile_id", "goals", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_goals_profile_id", table_name="goals")
    op.drop_table("goals")
