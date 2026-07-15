"""add family_invite_codes table (code-based family linking, no email needed)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 초대코드로 가족 연결: 이메일을 모르거나(카카오 소셜가입은 아직 임시 이메일이라 이메일
    # 방식이 안 먹힘) 이메일 방식이 번거로울 때 쓰는 대안 경로. 코드를 입력하는 즉시 연결되고
    # (승인 절차 없음), 1회용 + 유효시간(기본 30분)이 지나면 무효가 된다.
    op.create_table(
        "family_invite_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "guardian_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=6), nullable=False, unique=True),
        sa.Column("relation_label", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("family_invite_codes")
