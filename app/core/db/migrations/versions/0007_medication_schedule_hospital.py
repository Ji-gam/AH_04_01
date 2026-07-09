"""add: medication_schedules.hospital_name

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("medication_schedules", sa.Column("hospital_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("medication_schedules", "hospital_name")
