"""add agreement timestamps to users (T-AUTH-7 동의 순서/민감정보 별도동의)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("service_terms_agreed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("privacy_agreed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("sensitive_info_agreed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("marketing_agreed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "marketing_agreed_at")
    op.drop_column("users", "sensitive_info_agreed_at")
    op.drop_column("users", "privacy_agreed_at")
    op.drop_column("users", "service_terms_agreed_at")
