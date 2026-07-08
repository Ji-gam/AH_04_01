"""add refresh_token to users (T-AUTH-3 로그아웃 실무효화)

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
    op.add_column("users", sa.Column("refresh_token", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "refresh_token")
