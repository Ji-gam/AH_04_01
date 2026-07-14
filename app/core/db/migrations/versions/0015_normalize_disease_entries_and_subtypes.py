"""normalize diagnosis/family history into tables + disease_subtypes lookup table

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.disease_entries import SEED_DISEASE_SUBTYPES

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disease_subtypes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("category", "name", name="uq_disease_subtypes_category_name"),
    )

    op.create_table(
        "diagnosis_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.BigInteger(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disease", sa.String(length=30), nullable=False),
        sa.Column("disease_subtype_id", sa.BigInteger(), sa.ForeignKey("disease_subtypes.id"), nullable=True),
        sa.Column("diagnosed_years_ago", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("on_medication", sa.Boolean(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
    )

    op.create_table(
        "family_history_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.BigInteger(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disease", sa.String(length=30), nullable=False),
        sa.Column("disease_subtype_id", sa.BigInteger(), sa.ForeignKey("disease_subtypes.id"), nullable=True),
        sa.Column("relation", sa.String(length=15), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
    )

    # 큐레이션 시드 데이터 삽입 (원티드 스킬태그처럼 검색해서 바로 잡히는 흔한 질환명들).
    disease_subtypes_table = sa.table(
        "disease_subtypes",
        sa.column("category", sa.String),
        sa.column("name", sa.String),
        sa.column("is_custom", sa.Boolean),
    )
    seed_rows = [
        {"category": category, "name": name, "is_custom": False}
        for category, names in SEED_DISEASE_SUBTYPES.items()
        for name in names
    ]
    op.bulk_insert(disease_subtypes_table, seed_rows)

    # 기존 JSON 컬럼(diagnosis_history/family_history)은 이제 위 두 테이블로 대체되어 더 이상 안 쓴다.
    # [주의] 데이터 이관 없이 그냥 드롭한다 - 이번 PR 배포 전까지 실서비스 데이터가 없는 개발 단계라
    # 이관할 실사용자 데이터가 없다고 판단함. 만약 이미 입력해본 테스트 데이터를 보존해야 하면,
    # 이 마이그레이션 실행 전에 별도로 백업해둘 것.
    op.drop_column("profiles", "diagnosis_history")
    op.drop_column("profiles", "family_history")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("family_history", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("diagnosis_history", sa.JSON(), nullable=True))
    op.drop_table("family_history_entries")
    op.drop_table("diagnosis_entries")
    op.drop_table("disease_subtypes")
