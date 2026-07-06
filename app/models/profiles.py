from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profiles")
