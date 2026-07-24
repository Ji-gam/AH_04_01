"""add push_send_logs table (scheduler duplicate-send dedup claim)

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
        "push_send_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=False),
        sa.Column("sent_date", sa.Date(), nullable=False),
        sa.Column("sent_time", sa.String(length=5), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "source_type", "source_id", "sent_date", "sent_time", name="uq_push_send_logs_source_date_time"
        ),
    )


def downgrade() -> None:
    op.drop_table("push_send_logs")
