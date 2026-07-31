from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NoticeKind(StrEnum):
    NOTICE = "NOTICE"
    MARKETING = "MARKETING"


class Notice(Base):
    """서비스 자체 공지사항/마케팅 소식. 더보기 > 공지사항(NoticePage.tsx)에 실리던
    데이터를 백엔드로 옮긴 것 - 예전엔 프론트에 하드코딩된 배열이라 새 공지를 올려도
    알림을 보낼 방법이 없었다. kind로 알림설정(NotificationSettingsPage.tsx의
    notice_enabled/marketing_enabled)을 구분해서 발송 대상을 가른다."""

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[NoticeKind] = mapped_column(Enum(NoticeKind, native_enum=False, length=20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
