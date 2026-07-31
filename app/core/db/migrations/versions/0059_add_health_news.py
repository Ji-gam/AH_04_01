"""add health_news table (T-LLM-6 건강 뉴스 수집)

기존 health_contents(T-LLM-3)를 대체하는 새 테이블. health_contents DROP은 프론트가 새 API로
옮겨간 뒤 별도 리비전에서 수행한다(docs/tasks/T-LLM-6-health-news-feed.md 5절).

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "health_news",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("image_caption", sa.String(length=500), nullable=True),
        sa.Column("disease_code", sa.String(length=50), nullable=True),
        sa.Column("source_categories", sa.JSON(), nullable=True),
        sa.Column("card_summary", sa.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_url", name="uq_health_news_source_url"),
    )
    # 피드는 항상 발행일 최신순으로 읽는다 - 정렬 전용 인덱스.
    op.create_index("ix_health_news_published_at", "health_news", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_health_news_published_at", table_name="health_news")
    op.drop_table("health_news")
