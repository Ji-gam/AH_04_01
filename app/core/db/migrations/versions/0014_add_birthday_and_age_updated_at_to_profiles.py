"""replace age with a single birth_date column

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [재설계] 처음엔 실제 생년(연도)은 안 받고 "나이 직접입력 + 생일(월/일)"로 자동계산하려 했으나,
    # 카카오 비즈앱 전환 후 실제 생년월일을 그대로 받아올 가능성이 생겨서, 아예 처음부터 진짜
    # 생년월일(birth_date) 하나로 통합한다. 나이는 이제 저장 컬럼이 아니라 birth_date로부터
    # 매번 계산되는 값이다(app/services/age_calculator.py, Profile.age 프로퍼티 참고).
    # [주의] birth_month/birth_day/age_updated_at는 이 마이그레이션 체인에서 실제로 만들어진 적이
    # 없다(0013 시점엔 age 컬럼만 존재 - 0009에서 추가됨). age만 실제로 drop 대상이다.
    op.add_column("profiles", sa.Column("birth_date", sa.Date(), nullable=True))
    op.drop_column("profiles", "age")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("age", sa.Integer(), nullable=True))
    op.drop_column("profiles", "birth_date")
