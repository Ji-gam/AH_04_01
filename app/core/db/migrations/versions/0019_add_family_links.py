"""add family_links table with approval status (family registration MVP - dose sync deferred)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 보호자(guardian) -> 피보호자(member) 1:N 연결 요청. 예: 자녀 프로필 하나가 부모님 프로필
    # 여러 개를 관리할 수 있다(반대도 가능). 상대방(피보호자)이 수락해야 실제 권한이 생긴다 -
    # status가 ACCEPTED가 될 때까지는 요청 대기 상태(PENDING)다.
    #
    # [범위] 이번 PR은 등록/연결(승인 플로우 포함)까지만. 복약 확인·미루기 동기화
    # (medication_dose_events)는 별도 PR에서 다룬다.
    op.create_table(
        "family_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "guardian_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_profile_id",
            sa.BigInteger(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_label", sa.String(length=20), nullable=False),  # 예: "아버지", "어머니"
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACCEPTED", name="family_link_status", native_enum=False, length=10),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guardian_profile_id", "member_profile_id", name="uq_family_links_pair"),
    )
    op.create_check_constraint(
        "ck_family_links_not_self",
        "family_links",
        "guardian_profile_id <> member_profile_id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_family_links_not_self", "family_links", type_="check")
    op.drop_table("family_links")
