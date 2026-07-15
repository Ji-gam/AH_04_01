"""habit_subtype_suggestions: 세부 진단명별 AIWorkerGateway 생성 습관 캐시 테이블

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "habit_subtype_suggestions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("disease_subtype_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=50), nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["disease_subtype_id"],
            ["disease_subtypes.id"],
            name="fk_habit_subtype_suggestions_disease_subtype_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("disease_subtype_id", name="uq_habit_subtype_suggestions_disease_subtype_id"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("habit_subtype_suggestions")
