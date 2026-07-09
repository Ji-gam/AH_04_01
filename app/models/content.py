"""
T-LLM-3: 건강 콘텐츠 생성 파이프라인 캐시 테이블.
`user_id`/`profile_id`를 참조하지 않는다 — 개인 데이터가 아니라 질환(disease_code)
기준으로 전체 사용자가 공유하는 콘텐츠 캐시이기 때문이다(decision_log.md Tier 1:
"배치 생성 → 캐시 테이블 저장 → 화면은 캐시만 읽음"). 과거 날짜 카드는 삭제/교체하지
않고 누적해 "정보" 탭의 피드로 노출한다.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import JSON, Date, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContentCategory(StrEnum):
    LIFESTYLE = "LIFESTYLE"
    FOOD = "FOOD"
    MEDICAL_NEWS = "MEDICAL_NEWS"


class HealthContent(Base):
    __tablename__ = "health_contents"
    __table_args__ = (
        UniqueConstraint("disease_code", "category", "content_date", name="uq_health_content_disease_category_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    disease_code: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[ContentCategory] = mapped_column(
        SAEnum(ContentCategory, native_enum=False, length=20), nullable=False
    )
    content_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_prompt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
