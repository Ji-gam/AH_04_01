"""add notification_logs.link_url (알림 클릭 시 이동할 라우트)

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notification_logs", sa.Column("link_url", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("notification_logs", "link_url")
