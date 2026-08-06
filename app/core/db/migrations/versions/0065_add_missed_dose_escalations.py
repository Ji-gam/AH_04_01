"""add missed_dose_escalations table (F-NTFY-4 미확인시 가족알림)

Revision ID: 0065
Revises: 0064
Create Date: 2026-08-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "missed_dose_escalations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("medication_name", sa.String(length=100), nullable=False),
        sa.Column("alarm_time", sa.String(length=5), nullable=False),
        sa.Column("intake_date", sa.Date(), nullable=False),
        sa.Column("check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_missed_dose_escalations_profile_id", "missed_dose_escalations", ["profile_id"])
    op.create_index("ix_missed_dose_escalations_check_at", "missed_dose_escalations", ["check_at"])


def downgrade() -> None:
    op.drop_index("ix_missed_dose_escalations_check_at", table_name="missed_dose_escalations")
    op.drop_index("ix_missed_dose_escalations_profile_id", table_name="missed_dose_escalations")
    op.drop_table("missed_dose_escalations")
