"""change adherence_feedback_day_of_week default: Saturday(5) -> Sunday(6)

F-ADH-2 주간 순응도 피드백을 F-GOAL-3 주간 달성 리포트/주간 AI 리포트와 같은 요일(일요일)로
모아서, 한 주에 비슷한 리포트가 토/일/월 사흘에 걸쳐 따로따로 오지 않게 한다(2026-07-27).
기존 값이 여전히 옛 기본값(5)인 행만 새 기본값(6)으로 맞춘다 - 사용자가 이미 다른 요일로
직접 바꿔둔 행은 그대로 둔다(구분할 방법이 없어 "옛 기본값 그대로인 행 = 아직 커스터마이즈
안 한 행"으로 간주한다).

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "notification_settings",
        "adherence_feedback_day_of_week",
        existing_type=sa.Integer(),
        server_default="6",
    )
    op.execute(
        "UPDATE notification_settings SET adherence_feedback_day_of_week = 6 WHERE adherence_feedback_day_of_week = 5"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE notification_settings SET adherence_feedback_day_of_week = 5 WHERE adherence_feedback_day_of_week = 6"
    )
    op.alter_column(
        "notification_settings",
        "adherence_feedback_day_of_week",
        existing_type=sa.Integer(),
        server_default="5",
    )
