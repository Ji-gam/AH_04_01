from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PushPlatform(StrEnum):
    """지금은 WEB만 실제로 구현한다(웹푸시). iOS/Android는 나중에 Capacitor로 패키징할 때
    각각 APNs/FCM 디바이스 토큰을 저장하는 용도로 이 값만 추가하면 되게끔 미리 넣어둔다 -
    테이블을 새로 만들 필요 없이 이 enum에 값만 추가하고 `device_token` 컬럼을 쓰면 된다."""

    WEB = "WEB"
    IOS = "IOS"
    ANDROID = "ANDROID"


class PushSubscription(Base):
    """프로필별 푸시 구독 정보. 한 프로필이 여러 기기/브라우저에서 구독할 수 있어 1:N.

    웹푸시(WEB)는 `endpoint`+`p256dh_key`+`auth_key`(Web Push 표준, RFC 8291)를 쓰고,
    나중에 앱 패키징 시 추가될 IOS/ANDROID는 `device_token`(APNs/FCM 토큰) 하나만 쓰게 될
    것이다 - 그래서 웹 전용 컬럼들은 전부 nullable이다."""

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[PushPlatform] = mapped_column(
        SAEnum(PushPlatform, native_enum=False, length=10), default=PushPlatform.WEB, nullable=False
    )
    # 웹푸시(WEB) 전용 - Web Push 표준 3종 세트
    endpoint: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    p256dh_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    auth_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 네이티브 앱(IOS/ANDROID) 전용 - 지금은 안 씀, 나중에 패키징 시 사용
    device_token: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
