from datetime import datetime, time

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationSetting(Base):
    """프로필별 알림 커스터마이징 설정(무음 시간대, 알림 종류별 on/off 등). 예전엔 프론트
    (NotificationSettingsPage.tsx)가 localStorage에만 저장해서 기기를 바꾸거나 캐시를 지우면
    사라졌고, 실제 발송을 담당하는 push_scheduler.py도 이 설정을 전혀 몰라서 무음 시간대나
    "복약알림 끄기"를 지키지 않았다 - 이 테이블로 프로필당 한 행씩 저장해서 두 문제를 같이
    해결한다. sound/vibration/popup은 지금은 프론트 자체 테스트 알림(핸들러 handleSendTest)
    표시 방식에만 쓰이지만, 다른 필드와 같은 이유(기기 간 동기화)로 여기 같이 저장한다."""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    chatbot_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notice_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marketing_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lifestyle_tip_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_start: Mapped[time] = mapped_column(Time, default=time(22, 0), nullable=False)
    quiet_end: Mapped[time] = mapped_column(Time, default=time(7, 0), nullable=False)
    # F-ADH-2: 주간 순응도 피드백 발송 요일. Python date.weekday() 기준(월=0~일=6), 기본값
    # 5(토요일). 사용자가 알림설정 화면에서 바꿀 수 있다.
    adherence_feedback_day_of_week: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    vibration_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    popup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
