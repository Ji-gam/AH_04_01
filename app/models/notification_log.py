from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotificationLog(Base):
    """실제로 사용자에게 발송을 "시도"한 모든 알림(복약알림/공지/가족알림/주간·월간
    리포트/부작용안내/콘텐츠 알림 등)의 인앱 열람용 사본. PushService.send_to_profile()이
    호출될 때마다 한 건씩 쌓인다 - 브라우저 푸시 권한이 없거나 구독이 끊겨 실제 푸시가
    전달되지 않았더라도, "이 프로필에게 이 알림을 보내기로 결정했다"는 사실 자체는 여기에
    항상 남는다(홈 상단 🔔 알림함이 이 테이블을 그대로 보여준다)."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # 알림함에서 이 알림을 클릭했을 때 이동할 프론트 라우트(예: "/alarms", "/chat?autoMessage=...").
    # 없으면(예: 순응도 리포트처럼 딱 맞는 화면이 없는 경우) 클릭해도 아무 데도 이동하지 않는다.
    link_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
