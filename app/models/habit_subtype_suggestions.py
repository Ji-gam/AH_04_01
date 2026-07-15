from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HabitSubtypeSuggestion(Base):
    """세부 진단명(DiseaseSubtype)마다 AIWorkerGateway로 생성한 습관 1개를 캐싱해두는 테이블.
    같은 세부 진단명은 여러 사용자가 공유해도 되는 값이라(개인화 요소 없음) 진단명당 한 번만
    생성하고, 그 뒤로는 재사용한다 - 매 요청마다 LLM을 부르지 않는다(비용/지연시간 절감).
    disease_subtype_id에 unique 제약을 걸어 같은 진단명에 대해 중복 생성되지 않게 한다."""

    __tablename__ = "habit_subtype_suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    disease_subtype_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("disease_subtypes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
