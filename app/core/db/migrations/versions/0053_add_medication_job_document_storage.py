"""add medication recognition job document storage columns + guardian document access toggle (REQ-DOC-003)

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # REQ-DOC-003: 처방전/약봉투/진료기록 원본 이미지를 암호화 파일로 보관하기 위한 포인터
    # 컬럼들. 전부 nullable - 기존 job은 image_storage_key=NULL("이미지 없음"으로 취급)이고
    # 별도 백필이 필요 없다.
    op.add_column(
        "medication_recognition_jobs",
        sa.Column("image_storage_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "medication_recognition_jobs",
        sa.Column("image_mime_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "medication_recognition_jobs",
        sa.Column("image_size_bytes", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "medication_recognition_jobs",
        sa.Column("image_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 가족(보호자)에게 문서 이미지 공개 여부 - 기본 비공개(False), 본인이 켜야만 노출.
    op.add_column(
        "profiles",
        sa.Column(
            "allow_guardian_document_access",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "allow_guardian_document_access")
    op.drop_column("medication_recognition_jobs", "image_deleted_at")
    op.drop_column("medication_recognition_jobs", "image_size_bytes")
    op.drop_column("medication_recognition_jobs", "image_mime_type")
    op.drop_column("medication_recognition_jobs", "image_storage_key")
