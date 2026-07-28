"""add ai_chat/terms_of_service/marketing consent timestamps to users

Revision ID: 0051
Revises: 0050
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 회원가입 시 한 화면에서 한 번에 받는 통합 동의 - 이용약관/AI챗봇데이터활용/마케팅
    # (건강정보는 0050에서 이미 추가됨). 위치정보는 브라우저 자체 geolocation 권한
    # 요청으로 이미 다뤄지고 있어 별도 동의 항목을 안 둔다(2026-07-28 결정).
    op.add_column("users", sa.Column("ai_chat_consented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("terms_of_service_consented_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("marketing_consented_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "marketing_consented_at")
    op.drop_column("users", "terms_of_service_consented_at")
    op.drop_column("users", "ai_chat_consented_at")
