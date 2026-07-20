"""add push_subscriptions table (web push + future native app platform column)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-17

[주의] 로컬 dev가 이미 0020보다 앞서 있다면(다른 조원분 마이그레이션이 먼저 병합됐다면),
`alembic heads`로 실제 최신 리비전을 확인하고 이 파일의 `down_revision`을 그 값으로
바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 프로필별 푸시 구독 정보. 웹푸시(WEB)는 endpoint+p256dh_key+auth_key 3종 세트(Web Push
    # 표준, RFC 8291)를 쓴다. platform 컬럼은 나중에 앱 패키징(Capacitor) 시 IOS/ANDROID
    # 값을 추가하고 device_token(APNs/FCM 토큰) 컬럼만 채우면 되도록 미리 마련해뒀다 -
    # 그때 가서 테이블을 새로 만들 필요가 없다.
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.Enum("WEB", "IOS", "ANDROID", name="push_platform", native_enum=False, length=10),
            nullable=False,
            server_default="WEB",
        ),
        sa.Column("endpoint", sa.String(length=500), nullable=True, unique=True),
        sa.Column("p256dh_key", sa.String(length=200), nullable=True),
        sa.Column("auth_key", sa.String(length=100), nullable=True),
        sa.Column("device_token", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
