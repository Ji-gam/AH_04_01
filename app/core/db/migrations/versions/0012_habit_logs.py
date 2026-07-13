"""habit_logs: 홈 화면 생활습관 트래커(T-HOME-1) 오늘 진행량 저장 테이블

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("habit_key", sa.String(length=50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["profiles.id"], name="fk_habit_logs_profile_id_profiles", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("profile_id", "log_date", "habit_key", name="uq_habit_logs_profile_date_key"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("habit_logs")
