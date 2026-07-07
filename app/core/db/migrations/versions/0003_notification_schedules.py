"""add: notification_schedules

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_schedules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("medication_name", sa.String(length=100), nullable=False),
        sa.Column("frequency_type", sa.String(length=10), nullable=False, server_default="DAILY"),
        sa.Column("target_day_of_week", sa.String(length=10), nullable=True),
        sa.Column("alarm_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["profiles.id"], name="fk_notification_schedules_profile_id_profiles", ondelete="CASCADE"
        ),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("notification_schedules")
