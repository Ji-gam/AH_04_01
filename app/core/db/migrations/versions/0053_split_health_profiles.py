"""split health_profiles out of profiles (PII/health data separation, NFR-ARCH-001)

Revision ID: 0053
Revises: 0052
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [PII/건강정보 분리, NFR-ARCH-001] 원래 profiles 테이블 하나에 개인식별정보(이름/
    # 전화번호)와 건강정보(성별/생년월일/임신여부/키/몸무게/특이사항)가 같이 있어서,
    # diagnosis_entries 등을 profile_id로 조인하면 바로 "이름 → 진단병력"까지 이어지는
    # 문제가 있었다. health_profiles를 새로 만들어 건강 관련 컬럼을 전부 이관한다.
    #
    # special_notes/other_notes는 EncryptedText(암호화는 SQLAlchemy 레이어에서만 처리,
    # DB 컬럼 자체는 그냥 TEXT)라서, 아래 INSERT SELECT는 암호문을 그대로 복사할 뿐이고
    # 재암호화가 필요 없다 - 복호화는 여전히 애플리케이션에서 같은 키로 이뤄진다.
    op.create_table(
        "health_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("gender", sa.String(length=6), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("is_pregnant", sa.Boolean(), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("special_notes", sa.Text(), nullable=True),
        sa.Column("other_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.UniqueConstraint("profile_id", name="uq_health_profiles_profile_id"),
    )

    # 기존 profiles 데이터를 그대로 이관 - profiles에 있던 모든 행에 대해 1:1로 생성한다
    # (값이 전부 null이어도 행 자체는 만든다 - "모든 Profile은 health_profile을 갖는다"는
    # 불변식을 유지해야 age 프로퍼티 등 애플리케이션 코드가 None 체크만으로 안전함).
    op.execute(
        """
        INSERT INTO health_profiles
            (profile_id, gender, birth_date, is_pregnant, height_cm, weight_kg,
             special_notes, other_notes, created_at, updated_at)
        SELECT id, gender, birth_date, is_pregnant, height_cm, weight_kg,
               special_notes, other_notes, created_at, updated_at
        FROM profiles
        """
    )

    # profiles에서 건강 관련 컬럼 제거 - 이제 순수 개인식별정보(이름/전화번호)만 남는다.
    op.drop_column("profiles", "gender")
    op.drop_column("profiles", "birth_date")
    op.drop_column("profiles", "is_pregnant")
    op.drop_column("profiles", "height_cm")
    op.drop_column("profiles", "weight_kg")
    op.drop_column("profiles", "special_notes")
    op.drop_column("profiles", "other_notes")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("gender", sa.String(length=6), nullable=True))
    op.add_column("profiles", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("profiles", sa.Column("is_pregnant", sa.Boolean(), nullable=True))
    op.add_column("profiles", sa.Column("height_cm", sa.Numeric(5, 2), nullable=True))
    op.add_column("profiles", sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True))
    op.add_column("profiles", sa.Column("special_notes", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("other_notes", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE profiles p
        JOIN health_profiles hp ON hp.profile_id = p.id
        SET p.gender = hp.gender,
            p.birth_date = hp.birth_date,
            p.is_pregnant = hp.is_pregnant,
            p.height_cm = hp.height_cm,
            p.weight_kg = hp.weight_kg,
            p.special_notes = hp.special_notes,
            p.other_notes = hp.other_notes
        """
    )

    op.drop_table("health_profiles")
