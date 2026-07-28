from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SleepLog(Base):
    """REQ-TRCK-003: 하루 수면 기록 한 건. diet_logs/exercise_logs와 달리 하루에 여러 번
    기록하는 게 의미가 없어(자다 깬 걸 여러 건으로 나눠 적을 이유가 없음), (profile_id, log_date)
    유니크 제약을 두고 같은 날 다시 저장하면 덮어쓴다(서비스 레이어에서 upsert 처리).

    bed_time(취침 시각)은 참고용으로만 받고 기상 시각은 받지 않는다 - 수면 시간(hours)은
    사용자가 직접 입력한 값을 그대로 쓰고, 두 시각을 빼서 재계산하지 않는다."""

    __tablename__ = "sleep_logs"
    __table_args__ = (UniqueConstraint("profile_id", "log_date", name="uq_sleep_logs_profile_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    bed_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    # 5(매우 잘 잤음) ~ 1(1시간도 못 잠) - 낮을수록 안 좋음. AlarmPage 등 다른 5단계 스케일과
    # 방향을 맞췄다(높을수록 긍정적).
    quality: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # 수면의 질이 나쁠 때만(quality<=2) 프론트에서 입력칸을 보여준다 - 항상 nullable.
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
