from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.profiles import Disease, Gender


class WithdrawnHealthStat(Base):
    """탈퇴 시 익명화해서 남기는 통계 전용 레코드.

    profile_id/user_id/이름/이메일 등 식별정보는 일체 포함하지 않는다 - 이 테이블만 봐서는
    어떤 계정에서 나온 데이터인지 역추적이 원천적으로 불가능하다(완전 익명처리).
    나이도 정확한 생년월일 대신 10년 단위 나이대(age_group)로 일반화해서, 나이+성별+희귀질환
    조합으로 특정 개인이 간접 재식별될 위험을 줄인다. 구체적 질환명(disease_subtype)/자유메모
    (detail)는 재식별 위험이 있어 통계에는 포함하지 않고 대분류(disease)만 남긴다.

    법적 근거(개인정보보호법): 제21조(가명정보도 영구보관 대상 아님 - 별도 보관기간 운영 필요),
    제28조의2(통계작성 목적의 가명정보 처리는 별도 동의 불요). 팀 논의 내용은
    withdraw_data_policy_summary.md 참고.
    """

    __tablename__ = "withdrawn_health_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    disease: Mapped[Disease] = mapped_column(SAEnum(Disease, native_enum=False, length=30), nullable=False)
    is_family_history: Mapped[bool] = mapped_column(Boolean, nullable=False)  # False=본인 진단병력, True=가족력
    age_group: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 예: "30대". 미입력이면 null
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, native_enum=False, length=6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
