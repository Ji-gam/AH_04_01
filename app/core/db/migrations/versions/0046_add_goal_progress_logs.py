"""add goal_progress_logs (목표 일일 수치 기록)

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goal_progress_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("goal_id", sa.BigInteger(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_id", "log_date", name="uq_goal_progress_logs_goal_date"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_goal_progress_logs_goal_id", "goal_progress_logs", ["goal_id"])


def downgrade() -> None:
    op.drop_index("ix_goal_progress_logs_goal_id", table_name="goal_progress_logs")
    op.drop_table("goal_progress_logs")
