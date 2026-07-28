"""add health_info_consented_at to users (PIPA Article 23)

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 지금까지는 개인건강정보(민감정보) 제공동의를 브라우저 localStorage에만 기록해서
    # (ConsentPage.tsx의 markConsented), 서버에는 "언제 동의했는지" 근거가 전혀 안 남아있었다.
    # null이면 미동의, 값이 있으면 그 시각에 동의. (AI 챗봇 데이터 활용 동의는 위치/저장방식을
    # 더 논의하기로 해서 이번엔 같이 넣지 않는다 - 별도 논의 후 추가 예정)
    op.add_column("users", sa.Column("health_info_consented_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "health_info_consented_at")
