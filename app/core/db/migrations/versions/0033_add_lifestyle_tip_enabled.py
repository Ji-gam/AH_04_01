"""add lifestyle_tip_enabled to notification_settings (F-NTFY-6)

Revision ID: 0033
Revises: 0031
Create Date: 2026-07-22

[주의] 원래 0032로 작성했으나, 같은 시점에 열려있는 다른 PR(공지사항, notices 테이블
추가)이 같은 번호를 먼저 썼길래 0033으로 미리 재번호했다 - 로컬 dev가 이미 0031보다
앞서 있다면(다른 조원분 마이그레이션이 먼저 병합됐다면), `alembic heads`로 실제 최신
리비전을 확인하고 이 파일의 `down_revision`을 그 값으로 바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "lifestyle_tip_enabled")
