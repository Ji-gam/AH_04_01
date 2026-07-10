"""drop profiles.birthday column (age is now used instead)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 생년월일 대신 나이(age)를 직접 입력받는 방식으로 완전히 바뀌어서, birthday 컬럼 자체가 필요 없어졌다.
    op.drop_column("profiles", "birthday")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("birthday", sa.Date(), nullable=True))
