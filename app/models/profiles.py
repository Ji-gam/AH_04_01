from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.encrypted_types import EncryptedText
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
    from app.models.users import User


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class ProfileRelation(StrEnum):
    """향후 가족/서포터그룹 확장을 위한 값. 지금은 SELF만 실제로 발급된다."""

    SELF = "SELF"


class Disease(StrEnum):
    """진단병력/가족력에 쓰이는 5대질환 + 기타 고정값."""

    CANCER = "CANCER"
    HEART_DISEASE = "HEART_DISEASE"
    CEREBROVASCULAR_DISEASE = "CEREBROVASCULAR_DISEASE"
    DIABETES = "DIABETES"
    LIVER_DISEASE = "LIVER_DISEASE"
    OTHER = "OTHER"


class DiseaseStatus(StrEnum):
    """본인 진단병력의 조절상태 - AI가 상담 시 바로 참고할 수 있게 구조화된 값으로 받는다."""

    WELL_CONTROLLED = "WELL_CONTROLLED"  # 잘 조절됨
    MODERATE = "MODERATE"  # 보통
    UNCONTROLLED = "UNCONTROLLED"  # 조절안됨
    CURED = "CURED"  # 완치


class FamilyRelation(StrEnum):
    """가족력의 관계 - 혈연관계가 가까울수록 유전적 위험도 해석이 달라지므로 구조화된 값으로 받는다."""

    PARENT = "PARENT"  # 부모
    SIBLING = "SIBLING"  # 형제자매
    GRANDPARENT = "GRANDPARENT"  # 조부모
    OTHER = "OTHER"  # 기타


class Profile(Base):
    """계정(User)과 분리된 개인정보 + 도메인 데이터의 기준(profile_id). 한 User가 여러 Profile을 가질 수 있다.

    [가입 최소화] 가입 시점엔 name(닉네임)만 확정되고, gender/birth_date/phone_number는 전부 없는 채로
    생성된다. 성별/생년월일은 더보기 > 개인건강정보에서 입력받는다.

    [재설계] 처음엔 실제 생년(연도)을 안 받고 "나이 직접입력 + 생일(월/일)"만 받았으나, 카카오 비즈앱
    전환 후 실제 생년월일을 그대로 받아올 가능성이 생겨서 진짜 생년월일(birth_date) 하나로 통합했다.
    나이는 이제 저장 컬럼이 아니라 birth_date로부터 매번 계산되는 값이다(app.age 프로퍼티, 아래 참고).
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, native_enum=False, length=6), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [DUR 임부금기 경고 연동] 여태 채팅 쪽 임부금기 DUR 경고가 실제 데이터 없이 항상 False로
    # 고정돼있던 문제(#71)를 해결하기 위해 추가. 성별과 무관하게 그냥 선택 입력(주로 여성에게만
    # 화면에 노출하지만, 값 자체는 성별 제약 없이 저장 가능).
    is_pregnant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(11), nullable=True)
    relation: Mapped[ProfileRelation] = mapped_column(
        SAEnum(ProfileRelation, native_enum=False, length=10), default=ProfileRelation.SELF, nullable=False
    )
    # [개인건강정보] 전부 선택 입력 - 회원가입 흐름과는 무관하게 더보기 > 개인건강정보에서만 입력/수정한다.
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    # [개인정보보호법 제23조] 자유서술형 건강정보라 실제로 가장 민감한 내용이 들어갈 수
    # 있는 필드라, DB 암호화 대상으로 골랐다(2026-07-21) - EncryptedText 참고.
    special_notes: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # 특이사항
    other_notes: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # 기타
    # REQ-DOC-003: 처방전/약봉투/진료기록 원본 이미지는 복약스케줄보다 훨씬 민감한 개인정보라
    # 기본은 비공개(False)이며, 본인이 명시적으로 켜야만 연결된 보호자(가족)가 문서함에서
    # 원본 이미지를 조회할 수 있다. 삭제는 이 값과 무관하게 항상 본인만 가능하다.
    allow_guardian_document_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profiles")
    # [정규화] 진단병력/가족력은 JSON이 아니라 별도 테이블(app/models/disease_entries.py)로 관리한다.
    # MySQL에서 "당뇨인 사람 찾기" 같은 조회/집계가 JSON_EXTRACT 없이 바로 되고, 채팅 AI 연동 시에도
    # 구조화된 값을 그대로 SQL로 조회해서 넘길 수 있다.
    diagnosis_entries: Mapped[list["DiagnosisEntry"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    family_history_entries: Mapped[list["FamilyHistoryEntry"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )

    @property
    def age(self) -> int | None:
        """만 나이. birth_date로부터 그 자리에서 계산한다(DB에 저장된 값이 아니다).
        채팅/콘텐츠개인화 등 다른 도메인이 이미 `profile.age`로 읽고 있어서, 저장 방식이
        바뀌었어도 겉보기 인터페이스(속성 접근)는 그대로 유지한다."""
        if self.birth_date is None:
            return None
        from app.services.age_calculator import compute_age

        return compute_age(self.birth_date)

    @age.setter
    def age(self, value: int | None) -> None:
        """`profile.age = 76`처럼 직접 대입하는 기존 코드(주로 테스트)와의 호환을 위한 setter.
        오늘 날짜 기준으로 정확히 그 나이가 되도록 역산한 생년월일을 저장한다(오늘이 생일이라고
        가정 - 실제 생일은 모르니 어쩔 수 없는 근사치지만, 계산 결과 나이는 정확히 맞는다)."""
        if value is None:
            self.birth_date = None
            return
        today = date.today()
        self.birth_date = date(today.year - value, today.month, today.day)
