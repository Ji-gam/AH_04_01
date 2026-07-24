"""add diary_entries.image_base64 (사진 첨부 1장)

Revision ID: 0043
Revises: 0042
Create Date: 2026-07-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("diary_entries", sa.Column("image_base64", LONGTEXT(), nullable=True))


def downgrade() -> None:
    op.drop_column("diary_entries", "image_base64")
