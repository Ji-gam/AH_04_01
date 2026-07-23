"""add medication_intake_logs (F-ADH-1)

Revision ID: 0035
Revises: 0034
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medication_intake_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("scheduled_time", sa.String(length=5), nullable=False),
        sa.Column("intake_date", sa.Date(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "source_type", "source_id", "scheduled_time", "intake_date", name="uq_intake_item_per_day"
        ),
    )
    op.create_index(
        "ix_medication_intake_logs_profile_date",
        "medication_intake_logs",
        ["profile_id", "intake_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_medication_intake_logs_profile_date", table_name="medication_intake_logs")
    op.drop_table("medication_intake_logs")
