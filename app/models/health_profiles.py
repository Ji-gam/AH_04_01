from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.encrypted_types import EncryptedText
from app.models.base import Base
from app.models.profiles import Gender

if TYPE_CHECKING:
    from app.models.profiles import Profile


class HealthProfile(Base):
    """(2026-07-29) 개인식별정보(PII)와 건강정보를 물리적으로 분리 저장하기 위해
    `profiles` 테이블에서 떼어낸 건강 관련 필드 전용 테이블. `NFR-ARCH-001`("개인 식별
    정보와 건강 정보는 분리되어 저장되어, 한쪽이 유출되어도 다른 쪽과 쉽게 연결되지
    않는다") 대응 - `profiles`(이름/전화번호)와 여기(성별/생년월일/임신여부/키/몸무게/
    특이사항)를 분리했다.

    [설계] Profile과 1:1 관계이며, Profile 생성 시 항상 같이 생성된다(빈 값이어도) -
    `profile.health_profile`이 실무상 항상 존재한다는 불변식을 유지해서, `age` 프로퍼티
    등 기존 코드가 None 체크만으로 안전하게 동작하게 한다. Profile 삭제(회원탈퇴/가족
    연결해제) 시 cascade로 같이 삭제된다(개인정보보호법 제23조 - 탈퇴 시 지체없이 파기).
    """

    __tablename__ = "health_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id"), unique=True, nullable=False)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, native_enum=False, length=6), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [DUR 임부금기 경고 연동] 성별과 무관하게 선택 입력 가능(값 자체엔 성별 제약 없음).
    is_pregnant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # [개인정보보호법 제23조] 자유서술형이라 가장 민감한 내용이 들어갈 수 있어 암호화 대상.
    special_notes: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # 특이사항
    other_notes: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # 기타
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["Profile"] = relationship(back_populates="health_profile")
