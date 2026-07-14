from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.profiles import Disease, DiseaseStatus, FamilyRelation

if TYPE_CHECKING:
    from app.models.profiles import Profile

# 초기 시드 데이터. 국가암정보센터 발생순위 통계(암) + 일반적인 의학적 세부분류(나머지).
# "OTHER"(기타) 대분류는 처음부터 목록 없이 자유입력만 받는 성격이라 시드하지 않는다.
# [주의] 마이그레이션(0015)과 테스트(conftest.py)가 이 상수를 같이 참조한다 - 테스트 DB는
# 마이그레이션이 아니라 Base.metadata.create_all로 스키마만 만들어서, 마이그레이션 안에 있는
# 시드 INSERT문이 테스트 DB에는 안 들어가기 때문에 별도로 여기서 한 번 더 심어줘야 한다.
SEED_DISEASE_SUBTYPES: dict[str, list[str]] = {
    "CANCER": [
        "갑상선암",
        "폐암",
        "대장암",
        "유방암",
        "위암",
        "전립선암",
        "간암",
        "췌장암",
        "신장암",
        "방광암",
        "자궁경부암",
        "난소암",
        "백혈병",
    ],
    "HEART_DISEASE": ["협심증", "심근경색", "부정맥", "심부전", "심장판막질환", "심근병증"],
    "CEREBROVASCULAR_DISEASE": ["뇌경색", "뇌출혈", "일과성허혈발작", "지주막하출혈"],
    "DIABETES": ["제1형 당뇨병", "제2형 당뇨병", "임신성 당뇨병"],
    "LIVER_DISEASE": ["지방간", "A형간염", "B형간염", "C형간염", "간경변증", "간부전"],
}


class DiseaseSubtype(Base):
    """구체적 질환명 매핑테이블(예: 대분류 "암" 아래 "폐암"/"갑상선암"). 원티드 스킬태그 검색 방식처럼,
    사용자가 검색해서 기존 항목을 고르거나, 목록에 없으면 그 자리에서 새로 추가된다(is_custom=True).
    그렇게 계속 자라나는 목록이라, 나중에 같은 이름을 검색하는 다른 사용자에게도 정확히 매핑된다.

    같은 대분류(category) 안에서 이름 중복은 막는다(UniqueConstraint) - "폐암"이 두 번 따로 생기면
    검색/집계가 다시 파편화되기 때문.

    초기 데이터(암: 갑상선암/폐암/대장암/유방암/위암/전립선암/간암/췌장암/신장암/방광암/자궁경부암/
    난소암/백혈병, 심장질환/뇌혈관질환/당뇨/간질환 각각의 흔한 세부질환)는 마이그레이션에서
    is_custom=False로 미리 심어둔다. "기타" 대분류는 처음부터 목록이 없는 자유입력 성격이라
    미리 심어두는 항목이 없다.
    """

    __tablename__ = "disease_subtypes"
    __table_args__ = (UniqueConstraint("category", "name", name="uq_disease_subtypes_category_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category: Mapped[Disease] = mapped_column(SAEnum(Disease, native_enum=False, length=30), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_custom: Mapped[bool] = mapped_column(default=False, nullable=False)


class DiagnosisEntry(Base):
    """본인 진단병력 항목 하나. Profile 1:N. disease(대분류) 외 나머지는 전부 선택."""

    __tablename__ = "diagnosis_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    disease: Mapped[Disease] = mapped_column(SAEnum(Disease, native_enum=False, length=30), nullable=False)
    disease_subtype_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("disease_subtypes.id"), nullable=True)
    diagnosed_years_ago: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[DiseaseStatus | None] = mapped_column(
        SAEnum(DiseaseStatus, native_enum=False, length=20), nullable=True
    )
    on_medication: Mapped[bool | None] = mapped_column(nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["Profile"] = relationship(back_populates="diagnosis_entries")
    disease_subtype: Mapped["DiseaseSubtype | None"] = relationship()


class FamilyHistoryEntry(Base):
    """가족력 항목 하나. Profile 1:N. disease(대분류) 외 나머지는 전부 선택."""

    __tablename__ = "family_history_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    disease: Mapped[Disease] = mapped_column(SAEnum(Disease, native_enum=False, length=30), nullable=False)
    disease_subtype_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("disease_subtypes.id"), nullable=True)
    relation: Mapped[FamilyRelation | None] = mapped_column(
        SAEnum(FamilyRelation, native_enum=False, length=15), nullable=True
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["Profile"] = relationship(back_populates="family_history_entries")
    disease_subtype: Mapped["DiseaseSubtype | None"] = relationship()
