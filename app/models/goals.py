from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Goal(Base):
    """F-GOAL-1(목표 CRUD) + F-GOAL-2(목표 기반 AI 가이드)의 저장 단위. 관심 질병 등록은
    이미 diagnosis_entries(HealthInfoPage)가 하고 있어 여기서 다루지 않는다 - Goal은 순수
    "체중감량 3kg" 같은 수치 목표 하나다.

    진행률은 (current_value - start_value) / (target_value - start_value)로 계산한다(서비스
    레이어) - 이 공식이면 "줄이는 목표"(체중감량)와 "늘리는 목표"(수면시간 늘리기) 둘 다
    같은 식으로 자연스럽게 처리된다. current_value는 걷기/운동처럼 자동 집계할 기존 로그가
    있는 것도 있지만(ExerciseLog), 체중·수면처럼 히스토리 저장 인프라가 아예 없는 것도 있어
    MVP는 전부 사용자가 직접 갱신하는 방식으로 통일한다.

    guide_content/guide_generated_at은 F-GOAL-2 - 생성/수정 시 GoalService가 AI로 새로
    채운다(이력을 남기지 않고 항상 최신 1개만 유지)."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    start_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_achieved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guide_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    guide_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
