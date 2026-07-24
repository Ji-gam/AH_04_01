"""add exercise_logs.distance_km, exercise_logs.count (속도/개수 입력 지원)

Revision ID: 0040
Revises: 0039
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("exercise_logs", sa.Column("distance_km", sa.Numeric(6, 2), nullable=True))
    op.add_column("exercise_logs", sa.Column("count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("exercise_logs", "count")
    op.drop_column("exercise_logs", "distance_km")
