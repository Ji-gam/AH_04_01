"""health_contents: T-LLM-3 건강 콘텐츠 생성 파이프라인 캐시 테이블

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_contents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("disease_code", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("content_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_prompt", sa.String(length=500), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("disease_code", "category", "content_date", name="uq_health_content_disease_category_date"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("health_contents")
