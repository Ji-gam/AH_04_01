"""add withdrawn_health_stats table for anonymized statistics

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 회원탈퇴 시 진단병력/가족력을 완전 익명화해서 통계용으로 남기는 테이블. profile_id/user_id
    # 등 식별정보로 이어지는 컬럼이 하나도 없다 - 이 테이블만 봐서는 어떤 계정에서 나온 데이터인지
    # 역추적이 원천적으로 불가능하다(개인정보보호법 적용 대상인 "개인정보"가 아니게 됨).
    op.create_table(
        "withdrawn_health_stats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("disease", sa.String(length=30), nullable=False),
        sa.Column("is_family_history", sa.Boolean(), nullable=False),
        sa.Column("age_group", sa.String(length=10), nullable=True),
        sa.Column("gender", sa.String(length=6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("withdrawn_health_stats")
