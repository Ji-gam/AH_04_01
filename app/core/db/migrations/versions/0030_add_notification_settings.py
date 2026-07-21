"""add notification_settings table (per-profile push customization)

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-21

[주의] 로컬 dev가 이미 0029보다 앞서 있다면(다른 조원분 마이그레이션이 먼저 병합됐다면),
`alembic heads`로 실제 최신 리비전을 확인하고 이 파일의 `down_revision`을 그 값으로
바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("chatbot_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marketing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quiet_mode_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("quiet_start", sa.Time(), nullable=False, server_default="22:00:00"),
        sa.Column("quiet_end", sa.Time(), nullable=False, server_default="07:00:00"),
        sa.Column("sound_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("vibration_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("popup_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
