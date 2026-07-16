"""add food_drug_interaction tables (migrate reference data from SQLite to MySQL)

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "food_drug_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("published", sa.String(length=50), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("not_covered", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "food_drug_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=200), nullable=False),
        sa.Column("drug_class", sa.String(length=200), nullable=False),
        sa.Column("food_interaction", sa.Text(), nullable=True),
        sa.Column("alcohol_interaction", sa.Text(), nullable=True),
        sa.Column("source_page", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "food_drug_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("food_drug_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name_ko", sa.String(length=200), nullable=True),
        sa.Column("name_en", sa.String(length=200), nullable=True),
    )
    op.create_index("ix_food_drug_ingredients_category_id", "food_drug_ingredients", ["category_id"])
    op.create_index("ix_food_drug_ingredients_name_ko", "food_drug_ingredients", ["name_ko"])
    op.create_index("ix_food_drug_ingredients_name_en", "food_drug_ingredients", ["name_en"])

    op.create_table(
        "food_drug_food_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("food_drug_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("food_name", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "polarity",
            sa.Enum("avoid", "recommend", "timing_caution", name="polarity", native_enum=False, length=20),
            nullable=False,
            server_default="avoid",
        ),
    )
    op.create_index("ix_food_drug_food_items_category_id", "food_drug_food_items", ["category_id"])


def downgrade() -> None:
    op.drop_table("food_drug_food_items")
    op.drop_table("food_drug_ingredients")
    op.drop_table("food_drug_categories")
    op.drop_table("food_drug_sources")
