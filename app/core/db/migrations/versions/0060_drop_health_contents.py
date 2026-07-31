"""drop health_contents (T-LLM-3 → T-LLM-6 대체 완료)

건강정보 화면이 `health_news`(실제 언론사 기사)로 완전히 넘어가면서, LLM이 매일 지어낸
팁카드를 담던 `health_contents`는 읽는 코드가 하나도 남지 않았다. 관련 서비스/레포지토리/
DTO/라우터/관리자 화면/테스트를 모두 제거한 뒤 마지막으로 테이블을 내린다.

**되돌리기 어려운 마이그레이션이다.** downgrade는 빈 테이블만 다시 만든다 - 안에 있던
카드 내용은 복원할 수 없다(어차피 LLM이 매일 새로 만들던 캐시성 데이터였다).

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: Union[str, None] = "0059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("health_contents")


def downgrade() -> None:
    # 0006_health_contents.py가 만든 것과 같은 모양(데이터는 복원되지 않는다).
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
        sa.UniqueConstraint(
            "disease_code",
            "category",
            "content_date",
            name="uq_health_content_disease_category_date",
        ),
    )
