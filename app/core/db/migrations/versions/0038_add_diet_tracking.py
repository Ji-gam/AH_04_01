"""add diet_logs, food_nutrition_cache (F-DIET-1/2)

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diet_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("food_name", sa.String(length=150), nullable=False),
        sa.Column("serving_multiplier", sa.Numeric(3, 1), nullable=False),
        sa.Column("serving_grams", sa.Numeric(7, 1), nullable=False),
        sa.Column("calorie_kcal", sa.Numeric(7, 1), nullable=False),
        sa.Column("protein_g", sa.Numeric(6, 1), nullable=False),
        sa.Column("carb_g", sa.Numeric(6, 1), nullable=False),
        sa.Column("fat_g", sa.Numeric(6, 1), nullable=False),
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
    op.create_index("ix_diet_logs_profile_date", "diet_logs", ["profile_id", "log_date"])

    op.create_table(
        "food_nutrition_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("query_name", sa.String(length=150), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_name", name="uq_food_nutrition_cache_query_name"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("food_nutrition_cache")
    op.drop_index("ix_diet_logs_profile_date", table_name="diet_logs")
    op.drop_table("diet_logs")
