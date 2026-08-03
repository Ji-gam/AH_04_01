"""reason_feedbacks: 습관 추천 이유 / 식단 기준 칼로리 이유에 대한 사용자 평가(👍/👎)

Revision ID: 0062
Revises: 0061
Create Date: 2026-08-03

[주의] 로컬 dev가 이미 0061보다 앞서 있다면(다른 조원분 마이그레이션이 먼저 병합됐다면),
`alembic heads`로 실제 최신 리비전을 확인하고 이 파일의 `down_revision`을 그 값으로
바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reason_feedbacks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "feature",
            sa.Enum("HABIT_REASON", "DIET_KCAL_REASON", name="reason_feedback_feature", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("target_key", sa.String(length=100), nullable=False),
        sa.Column(
            "value",
            sa.Enum("UP", "DOWN", name="reason_feedback_value", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_reason_feedbacks_profile_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("profile_id", "feature", "target_key", name="uq_reason_feedbacks_profile_feature_target"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("reason_feedbacks")
