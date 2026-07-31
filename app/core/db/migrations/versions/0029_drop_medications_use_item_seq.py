"""drop medications table, MedicationSchedule now references item_seq directly

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-20

(T-MED-16) `medications`(자체 캐시 테이블)를 없애고 원본 약품 마스터 데이터
(`drugs_data`/`drug_identification` 등, 이미 MySQL에 전량 적재됨)의 `item_seq`를
`medication_schedules`가 직접 참조하도록 바꾼다. `item_seq`는 저 테이블들에서 row 단위
UNIQUE가 아니라 DB FK를 걸 수 없음(사용자 확정 — 앱 레벨에서만 존재 검증).

**주의 — 되돌릴 수 없는 데이터 손실**: 사용자 확정에 따라 기존 `medication_schedules`(23건)를
이관하지 않고 버린다. `upgrade()`/`downgrade()` 둘 다 이 테이블을 비운다
(medication_id ↔ item_seq를 상호 변환할 방법이 없어 downgrade도 데이터를 복구하지 못한다).

[주의] 로컬 dev가 이미 0028보다 앞서 있다면 `alembic heads`로 실제 최신 리비전을 확인하고
이 파일의 `down_revision`을 그 값으로 바꿔주세요.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _find_fk_name(table: str, column: str, referenced_table: str) -> str | None:
    bind = op.get_bind()
    return bind.execute(
        sa.text(
            "SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column "
            "AND REFERENCED_TABLE_NAME = :referenced_table"
        ),
        {"table": table, "column": column, "referenced_table": referenced_table},
    ).scalar()


def upgrade() -> None:
    fk_name = _find_fk_name("medication_schedules", "medication_id", "medications")
    if fk_name:
        op.drop_constraint(fk_name, "medication_schedules", type_="foreignkey")

    # 기존 23건은 이관하지 않고 버린다(사용자 확정) - medication_id -> item_seq로 변환할 방법이 없다.
    op.execute("DELETE FROM medication_schedules")

    op.drop_column("medication_schedules", "medication_id")
    op.add_column("medication_schedules", sa.Column("item_seq", sa.String(length=20), nullable=False))
    op.create_index("ix_medication_schedules_item_seq", "medication_schedules", ["item_seq"])
    op.add_column("medication_schedules", sa.Column("display_name", sa.String(length=150), nullable=True))

    op.drop_table("medications")


def downgrade() -> None:
    op.create_table(
        "medications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("standard_code", sa.String(length=50), nullable=True),
        sa.Column("medication_name", sa.String(length=150), nullable=False),
        sa.Column("form_type", sa.String(length=30), nullable=True),
        sa.Column("dosage_guideline", sa.Text(), nullable=True),
        sa.Column("side_effects", sa.Text(), nullable=True),
        sa.Column("precautions", sa.Text(), nullable=True),
        sa.Column("storage_method", sa.Text(), nullable=True),
        sa.Column("shape", sa.String(length=30), nullable=True),
        sa.Column("color", sa.String(length=30), nullable=True),
        sa.Column("letters", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # item_seq -> medication_id로 되돌릴 방법이 없으므로 downgrade도 데이터를 폐기한다.
    op.execute("DELETE FROM medication_schedules")

    op.drop_column("medication_schedules", "display_name")
    op.drop_index("ix_medication_schedules_item_seq", table_name="medication_schedules")
    op.drop_column("medication_schedules", "item_seq")
    op.add_column("medication_schedules", sa.Column("medication_id", sa.BigInteger(), nullable=False))
    op.create_foreign_key(
        "medication_schedules_medication_id_fkey",
        "medication_schedules",
        "medications",
        ["medication_id"],
        ["id"],
        ondelete="CASCADE",
    )
