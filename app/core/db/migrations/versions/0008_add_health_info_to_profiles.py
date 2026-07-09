"""add health info columns to profiles

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("height_cm", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("profiles", sa.Column("weight_kg", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("profiles", sa.Column("diagnosis_history", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("family_history", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("special_notes", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("other_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "other_notes")
    op.drop_column("profiles", "special_notes")
    op.drop_column("profiles", "family_history")
    op.drop_column("profiles", "diagnosis_history")
    op.drop_column("profiles", "weight_kg")
    op.drop_column("profiles", "height_cm")
