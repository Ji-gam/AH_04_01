"""habit_diagnosis_entry_suggestions: 세부 진단명 없는 자유텍스트 진단 항목별 AI 생성 습관 캐시 테이블

Revision ID: 0064
Revises: 0063
Create Date: 2026-08-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habit_diagnosis_entry_suggestions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("diagnosis_entry_id", sa.BigInteger(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["diagnosis_entry_id"],
            ["diagnosis_entries.id"],
            name="fk_habit_diagnosis_entry_suggestions_diagnosis_entry_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("diagnosis_entry_id", "slot", name="uq_habit_diagnosis_entry_suggestions_entry_slot"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("habit_diagnosis_entry_suggestions")
