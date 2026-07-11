"""add sns_provider/sns_id to users, make hashed_password nullable

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("sns_provider", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("sns_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_sns_provider_sns_id", "users", ["sns_provider", "sns_id"])
    # 소셜 로그인 계정은 비밀번호가 없다 - 이메일 가입자만 값이 있어야 하므로 nullable로 변경.
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=128), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=128), nullable=False)
    op.drop_constraint("uq_users_sns_provider_sns_id", "users", type_="unique")
    op.drop_column("users", "sns_id")
    op.drop_column("users", "sns_provider")
