from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.users import User


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class ProfileRelation(StrEnum):
    """향후 가족/서포터그룹 확장을 위한 값. 지금은 SELF만 실제로 발급된다."""

    SELF = "SELF"


class Disease(StrEnum):
    """[T-PROFILE-1] RAG(진단병력/가족력) 입력용 5대질환. 목록에 없으면 빈 리스트([])로 표현한다."""

    CANCER = "CANCER"  # 암
    HEART_DISEASE = "HEART_DISEASE"  # 심장질환
    CEREBROVASCULAR_DISEASE = "CEREBROVASCULAR_DISEASE"  # 뇌혈관질환
    DIABETES = "DIABETES"  # 당뇨
    LIVER_DISEASE = "LIVER_DISEASE"  # 간질환


class Profile(Base):
    """계정(User)과 분리된 개인정보 + 도메인 데이터의 기준(profile_id). 한 User가 여러 Profile을 가질 수 있다."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[Gender] = mapped_column(SAEnum(Gender, native_enum=False, length=6), nullable=False)
    birthday: Mapped[date] = mapped_column(Date, nullable=False)
    phone_number: Mapped[str] = mapped_column(String(11), nullable=False)
    relation: Mapped[ProfileRelation] = mapped_column(
        SAEnum(ProfileRelation, native_enum=False, length=10), default=ProfileRelation.SELF, nullable=False
    )
    # [T-PROFILE-1 생체정보] RAG 조원(복약/알림 담당) 요청으로 추가. 회원가입 직후 별도 화면에서 입력받는다.
    # 소셜로그인은 셋 다 제공하지 않아 전부 null로 시작 - 이 화면이 소셜 가입자에게도 그대로 필요하다.
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    diagnosis_history: Mapped[list[str] | None] = mapped_column(JSON, default=list, nullable=True)
    family_history: Mapped[list[str] | None] = mapped_column(JSON, default=list, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profiles")
