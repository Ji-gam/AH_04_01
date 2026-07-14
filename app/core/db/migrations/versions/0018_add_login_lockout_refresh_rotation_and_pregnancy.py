"""add login lockout fields, issued_refresh_tokens table, and profile.is_pregnant

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 로그인 시도 제한(브루트포스 방어)
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    # 리프레시 토큰 로테이션 + 재사용 탐지용 추적 테이블
    op.create_table(
        "issued_refresh_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("jti", sa.String(length=32), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_issued_refresh_tokens_jti"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_issued_refresh_tokens_user_id_users", ondelete="CASCADE"
        ),
        mysql_charset="utf8mb4",
    )

    # 임신 여부 (DUR 임부금기 경고 실연동용, #71)
    op.add_column("profiles", sa.Column("is_pregnant", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "is_pregnant")
    op.drop_table("issued_refresh_tokens")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
