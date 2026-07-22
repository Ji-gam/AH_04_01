"""add notices table (공지사항/마케팅 소식)

Revision ID: 0032
Revises: 0031
Create Date: 2026-07-22

[주의] 로컬 dev가 이미 0031보다 앞서 있다면(다른 조원분 마이그레이션이 먼저 병합됐다면),
`alembic heads`로 실제 최신 리비전을 확인하고 이 파일의 `down_revision`을 그 값으로
바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "kind",
            sa.Enum("NOTICE", "MARKETING", name="notice_kind", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notices")
