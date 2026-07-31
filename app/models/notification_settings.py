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
    # F-NTFY-6: 라이프스타일 팁 전용 시간대 - 기존 quiet_start/quiet_end(전체 비필수 알림
    # 공용 무음시간대)와 별개로, 팁만 더 좁혀 받고 싶은 사용자를 위한 추가 옵션. 기본값 꺼짐
    # (꺼져있으면 quiet_start/quiet_end만 적용되어 기존 동작과 동일).
    lifestyle_tip_window_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lifestyle_tip_start: Mapped[time] = mapped_column(Time, default=time(9, 0), nullable=False)
    lifestyle_tip_end: Mapped[time] = mapped_column(Time, default=time(21, 0), nullable=False)
    # F-NTFY-6: 라이프스타일 팁 수신 빈도 - 마지막으로 받은 지 이 일수가 지나야 다음 팁을
    # 받는다. 0이면(기본값) 제한 없음(콘텐츠가 생성될 때마다 매번 받음).
    lifestyle_tip_min_interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 위 빈도 제한 판정용 - 사용자가 직접 설정하는 값이 아니라 발송 시점마다 서버가
    # 갱신하는 내부 기록이라 API 응답/수정 대상에는 포함하지 않는다.
    lifestyle_tip_last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quiet_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_start: Mapped[time] = mapped_column(Time, default=time(22, 0), nullable=False)
    quiet_end: Mapped[time] = mapped_column(Time, default=time(7, 0), nullable=False)
    # F-ADH-2: 주간 순응도 피드백 발송 요일. Python date.weekday() 기준(월=0~일=6), 기본값
    # 6(일요일) - F-GOAL-3 주간 달성 리포트도 일요일로 맞춰서, 여러 요일에 걸쳐 비슷한 주간
    # 요약 알림이 따로따로 오지 않고 한 번에 몰아서 오게 한다(2026-07-27). 사용자가
    # 알림설정 화면에서 바꿀 수 있다.
    adherence_feedback_day_of_week: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    vibration_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    popup_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
