"""add error_logs table (전역 예외 핸들러가 기록하는 앱 전체 오류 로그)

Revision ID: 0052
Revises: 0051
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AI챗봇 오류는 이미 로그 파일에 "예외타입/글자수만" 남기고 있었는데(개인정보 제거,
    # 2026-07 초), 앱 전체(챗봇 외 나머지 API)는 예외가 나도 도커 로그에만 흘러가고
    # DB에 남거나 조회할 방법이 없었다. 이 테이블 + main.py의 전역 예외 핸들러가 그
    # 공백을 메운다. 같은 이유로 전체 트레이스백/요청바디는 저장하지 않고, 예외 타입과
    # 잘라낸 메시지, 경로/메서드 정도만 남긴다.
    op.create_table(
        "error_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("exception_type", sa.String(length=100), nullable=False),
        # 원문 예외 메시지는 스택트레이스나 쿼리 파라미터 등 민감정보를 포함할 수 있어
        # 200자로 잘라서 남긴다(전체 트레이스백은 도커 로그에만, DB엔 안 남김).
        sa.Column("message", sa.String(length=200), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_created_at", "error_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_error_logs_created_at", table_name="error_logs")
    op.drop_table("error_logs")
