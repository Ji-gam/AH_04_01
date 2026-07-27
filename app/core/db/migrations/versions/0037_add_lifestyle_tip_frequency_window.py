"""add lifestyle tip frequency/window settings (F-NTFY-6)

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_window_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_start", sa.Time(), server_default="09:00:00", nullable=False),
    )
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_end", sa.Time(), server_default="21:00:00", nullable=False),
    )
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_min_interval_days", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "lifestyle_tip_last_sent_at")
    op.drop_column("notification_settings", "lifestyle_tip_min_interval_days")
    op.drop_column("notification_settings", "lifestyle_tip_end")
    op.drop_column("notification_settings", "lifestyle_tip_start")
    op.drop_column("notification_settings", "lifestyle_tip_window_enabled")
