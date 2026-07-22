"""add lifestyle_tip_enabled to notification_settings (F-NTFY-6)

Revision ID: 0033
Revises: 0032
Create Date: 2026-07-22

[주의] 원래 0032로 작성했다가, 같은 시점에 열려있던 다른 PR(공지사항, notices 테이블
추가)이 같은 번호를 먼저 썼길래 0033으로 재번호했다. 그때 revision만 바꾸고
down_revision을 여전히 0031로 둬서, 두 PR이 모두 머지된 뒤 0031 밑에 0032/0033이
갈라지는 마이그레이션 포크가 생겼다(`alembic heads`가 head 2개를 보고했음) - 여기서
down_revision을 0032로 바로잡아 0031→0032→0033 단일 체인으로 되돌린다. 로컬 dev가
이미 0032보다 앞서 있다면 `alembic heads`로 실제 최신 리비전을 확인하고 이 파일의
`down_revision`을 그 값으로 바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_settings",
        sa.Column("lifestyle_tip_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "lifestyle_tip_enabled")
