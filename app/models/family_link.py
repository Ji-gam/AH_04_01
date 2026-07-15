from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FamilyLinkStatus(StrEnum):
    PENDING = "PENDING"  # 보호자가 요청을 보냈고, 상대방(피보호자)의 응답 대기 중
    ACCEPTED = "ACCEPTED"  # 상대방이 수락 - 이 상태여야만 실제 보호자 권한(약 등록 등)이 생긴다


class FamilyLink(Base):
    """보호자(guardian) -> 피보호자(member) 연결 요청/승인. 예: 자녀 프로필이 부모님 프로필을
    관리하고 싶다고 요청하면, 부모님이 수락해야 실제로 연결된다(#가족관리 승인 플로우).

    상대방 동의 없이 임의로 연결되면 안 되므로, 생성 시점엔 항상 PENDING이고 요청받은 쪽
    (member)만 ACCEPTED로 바꿀 수 있다. 아직 정식 푸시 알림 인프라가 없어, "알림"은 실시간
    푸시가 아니라 피보호자가 가족관리 화면을 열었을 때 대기중인 요청으로 보이는 방식이다.
    """

    __tablename__ = "family_links"
    __table_args__ = (
        UniqueConstraint("guardian_profile_id", "member_profile_id", name="uq_family_links_pair"),
        CheckConstraint("guardian_profile_id <> member_profile_id", name="ck_family_links_not_self"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guardian_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    member_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    relation_label: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[FamilyLinkStatus] = mapped_column(
        SAEnum(FamilyLinkStatus, native_enum=False, length=10),
        default=FamilyLinkStatus.PENDING,
        server_default=FamilyLinkStatus.PENDING.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
