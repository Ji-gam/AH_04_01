"""add adherence_feedback_day_of_week (F-ADH-2)

Revision ID: 0036
Revises: 0035
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("adherence_feedback_day_of_week", sa.Integer(), server_default="5", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "adherence_feedback_day_of_week")
