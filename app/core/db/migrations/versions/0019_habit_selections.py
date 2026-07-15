"""habit_selections: 오늘의 추천 습관 중 사용자가 실제로 고른 항목(최대 5개) 저장 테이블

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habit_selections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("select_date", sa.Date(), nullable=False),
        sa.Column("habit_key", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["profiles.id"], name="fk_habit_selections_profile_id_profiles", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("profile_id", "select_date", "habit_key", name="uq_habit_selections_profile_date_key"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("habit_selections")
