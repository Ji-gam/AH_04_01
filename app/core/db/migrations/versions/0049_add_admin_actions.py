"""add admin_actions table (관리자 화면 - 권한변경/공지발송 감사로그)

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # "누가 언제 누구를 관리자로 지정했는지", "누가 언제 어떤 공지를 보냈는지"를 남기는 감사로그.
    # 관리자 기능은 공용 가입코드 없이 "기존 관리자가 화면에서 승격" 방식으로만 늘어나므로,
    # 이 기록이 유일한 추적 수단이다.
    op.create_table(
        "admin_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        # 대상(target)은 액션 종류에 따라 user_id일 수도, notice_id일 수도 있어 범용 문자열로 둔다.
        sa.Column("target", sa.String(length=100), nullable=True),
        # 사람이 읽을 요약(예: "grant admin to user 12", "notice 'xxx' sent to 34 profiles").
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_actions_actor_user_id", "admin_actions", ["actor_user_id"])
    op.create_index("ix_admin_actions_created_at", "admin_actions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_actions_created_at", table_name="admin_actions")
    op.drop_index("ix_admin_actions_actor_user_id", table_name="admin_actions")
    op.drop_table("admin_actions")
