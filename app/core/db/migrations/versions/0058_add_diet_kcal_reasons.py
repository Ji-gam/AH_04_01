"""diet_kcal_reasons: 개인화된 기준 칼로리 + AI 생성 한 줄 이유 캐시 테이블

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diet_kcal_reasons",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("reference_kcal", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_diet_kcal_reasons_profile_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("profile_id", "log_date", name="uq_diet_kcal_reasons_profile_date"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("diet_kcal_reasons")
