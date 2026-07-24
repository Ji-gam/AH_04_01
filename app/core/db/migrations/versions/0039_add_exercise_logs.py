"""add exercise_logs (운동 기록)

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercise_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("exercise_name", sa.String(length=100), nullable=False),
        sa.Column("duration_minutes", sa.Numeric(6, 1), nullable=False),
        sa.Column("calorie_kcal", sa.Numeric(7, 1), nullable=False),
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
    op.create_index("ix_exercise_logs_profile_date", "exercise_logs", ["profile_id", "log_date"])


def downgrade() -> None:
    op.drop_index("ix_exercise_logs_profile_date", table_name="exercise_logs")
    op.drop_table("exercise_logs")
