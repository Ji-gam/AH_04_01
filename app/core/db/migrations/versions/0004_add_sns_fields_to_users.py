"""add sns fields to users (social login)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("sns_provider", sa.String(length=20), nullable=False, server_default="LOCAL"),
    )
    op.add_column("users", sa.Column("sns_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "sns_id")
    op.drop_column("users", "sns_provider")
