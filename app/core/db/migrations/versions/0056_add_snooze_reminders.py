"""add snooze_reminders table (F-NTFY-3 미루기)

Revision ID: 0056
Revises: 0055
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: Union[str, None] = "0055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snooze_reminders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("medication_name", sa.String(length=100), nullable=False),
        sa.Column("alarm_time", sa.String(length=5), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_snooze_reminders_profile_id", "snooze_reminders", ["profile_id"])
    op.create_index("ix_snooze_reminders_remind_at", "snooze_reminders", ["remind_at"])


def downgrade() -> None:
    op.drop_index("ix_snooze_reminders_remind_at", table_name="snooze_reminders")
    op.drop_index("ix_snooze_reminders_profile_id", table_name="snooze_reminders")
    op.drop_table("snooze_reminders")
