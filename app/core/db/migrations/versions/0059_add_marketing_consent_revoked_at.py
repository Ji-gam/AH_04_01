"""add marketing_consent_revoked_at to users (마케팅 동의 껐다켰다 지원)

Revision ID: 0058
Revises: 0057
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
    # 마케팅 동의는 필수 3종(이용약관/건강정보/AI챗봇)과 달리 선택 항목이라 유일하게
    # 다시 껐다 켤 수 있게 만든다 - "동의 시각"과 별개로 "철회 시각"을 남겨서, 관리자
    # 화면에서 "언제 동의했다가 언제 취소했는지"를 둘 다 볼 수 있게 한다.
    op.add_column("users", sa.Column("marketing_consent_revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "marketing_consent_revoked_at")
