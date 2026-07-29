from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
    from app.models.health_profiles import HealthProfile
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

    [가입 최소화] 가입 시점엔 name(닉네임)만 확정되고, phone_number는 없는 채로 생성된다.

    [2026-07-29 PII/건강정보 분리] 성별/생년월일/임신여부/키/몸무게/특이사항은 원래 이
    테이블에 같이 있었으나(`NFR-ARCH-001` "개인 식별 정보와 건강 정보는 분리되어 저장"
    요구사항 위반이었음), `health_profiles` 테이블로 전부 이관했다. 이 테이블(`profiles`)엔
    이제 순수 개인식별정보(이름/전화번호)만 남는다. `age` 프로퍼티 등 기존 코드와의 호환을
    위해 `profile.health_profile.birth_date`를 대신 참조하도록 프로퍼티로 감싸뒀다 -
    `profile.age`처럼 겉보기 인터페이스는 그대로 유지된다.
    """

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(11), nullable=True)
    relation: Mapped[ProfileRelation] = mapped_column(
        SAEnum(ProfileRelation, native_enum=False, length=10), default=ProfileRelation.SELF, nullable=False
    )
    # REQ-DOC-003: 처방전/약봉투/진료기록 원본 이미지는 복약스케줄보다 훨씬 민감한 개인정보라
    # 기본은 비공개(False)이며, 본인이 명시적으로 켜야만 연결된 보호자(가족)가 문서함에서
    # 원본 이미지를 조회할 수 있다. 삭제는 이 값과 무관하게 항상 본인만 가능하다.
    # (2026-07-29 PII/건강정보 분리 - 이 필드는 접근권한 플래그라 건강정보가 아니므로
    # profiles에 그대로 둔다. height_cm/weight_kg/special_notes/other_notes는
    # health_profiles로 이관됐다.)
    allow_guardian_document_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profiles")
    # [PII/건강정보 분리] 1:1 - Profile 생성 시 항상 같이 생성된다(빈 값이어도). Profile
    # 삭제 시 cascade로 같이 삭제(탈퇴 시 지체없이 파기 원칙 유지).
    # [안전장치] lazy="selectin"으로 Profile을 로드할 때마다 자동으로 같이 조회되게 한다 -
    # 이 필드들이 원래 Profile에 직접 있던 걸 분리해낸 거라, 호출부마다 일일이
    # selectinload(Profile.health_profile)을 챙기게 하면 하나라도 빠뜨렸을 때 async
    # 세션에서 조용히 MissingGreenlet 에러가 나거나(최악의 경우 이 개발 단계에선 에러로
    # 바로 드러나서 그나마 다행이지만) 놓치기 쉽다 - 기본값 자체를 안전하게 만든다.
    health_profile: Mapped["HealthProfile"] = relationship(
        back_populates="profile", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
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
        """만 나이. health_profile.birth_date로부터 그 자리에서 계산한다(DB에 저장된
        값이 아니다). 채팅/콘텐츠개인화 등 다른 도메인이 이미 `profile.age`로 읽고
        있어서, 저장 위치가 바뀌었어도 겉보기 인터페이스(속성 접근)는 그대로 유지한다."""
        if self.health_profile is None or self.health_profile.birth_date is None:
            return None
        from app.services.age_calculator import compute_age

        return compute_age(self.health_profile.birth_date)

    @age.setter
    def age(self, value: int | None) -> None:
        """`profile.age = 76`처럼 직접 대입하는 기존 코드(주로 테스트)와의 호환을 위한 setter.
        오늘 날짜 기준으로 정확히 그 나이가 되도록 역산한 생년월일을 저장한다(오늘이 생일이라고
        가정 - 실제 생일은 모르니 어쩔 수 없는 근사치지만, 계산 결과 나이는 정확히 맞는다).
        health_profile이 아직 없으면(불변식이 깨진 예외적 상황) 새로 만들어서 대입한다."""
        from app.models.health_profiles import HealthProfile

        if self.health_profile is None:
            self.health_profile = HealthProfile()
        if value is None:
            self.health_profile.birth_date = None
            return
        today = date.today()
        self.health_profile.birth_date = date(today.year - value, today.month, today.day)
