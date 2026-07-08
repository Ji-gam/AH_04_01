"""add biometric info to profiles (T-PROFILE-1)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("height_cm", sa.Float(), nullable=True))
    op.add_column("profiles", sa.Column("weight_kg", sa.Float(), nullable=True))
    # MySQL은 JSON 컬럼에 리터럴 DEFAULT를 허용하지 않는다 -> nullable로 두고,
    # 애플리케이션(모델/서비스) 레벨에서 null을 빈 리스트로 취급한다.
    op.add_column("profiles", sa.Column("diagnosis_history", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("family_history", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "family_history")
    op.drop_column("profiles", "diagnosis_history")
    op.drop_column("profiles", "weight_kg")
    op.drop_column("profiles", "height_cm")
