"""relax profile required fields (gender/birthday/phone_number nullable), add age column

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [가입 최소화] 가입 시 name(닉네임)+email+password만 받게 되면서, 가입 시점에 gender/birthday/
    # phone_number를 채울 수 없게 됐다. 셋 다 nullable로 완화하고, "나이"를 직접 입력받는 age 컬럼을 추가한다.
    op.alter_column("profiles", "gender", existing_type=sa.String(length=6), nullable=True)
    op.alter_column("profiles", "birthday", existing_type=sa.Date(), nullable=True)
    op.alter_column("profiles", "phone_number", existing_type=sa.String(length=11), nullable=True)
    op.add_column("profiles", sa.Column("age", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "age")
    op.alter_column("profiles", "phone_number", existing_type=sa.String(length=11), nullable=False)
    op.alter_column("profiles", "birthday", existing_type=sa.Date(), nullable=False)
    op.alter_column("profiles", "gender", existing_type=sa.String(length=6), nullable=False)
