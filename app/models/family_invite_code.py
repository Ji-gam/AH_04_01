import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 카카오 소셜가입은 아직 임시 이메일(kakao_xxx@social.local)이라 이메일로 가족을 찾는 방식이
# 안 먹힌다. 초대코드는 이메일과 무관하게 동작해서 그 대안이 된다. 나중에 카카오 비즈앱으로
# 전환해서 실제 이메일을 받아올 수 있게 되면, 이메일 요청 방식도 그대로 다시 쓸 수 있으니
# 이 모델/코드를 따로 없앨 필요는 없다 - 그냥 두 경로를 계속 같이 제공하면 된다.

INVITE_CODE_LENGTH = 6
# 헷갈리기 쉬운 문자(0/O, 1/I/L) 제외 - 연로하신 분이 코드를 옮겨 적을 때 실수를 줄이기 위함.
INVITE_CODE_ALPHABET = "".join(c for c in (string.ascii_uppercase + string.digits) if c not in "0O1IL")
INVITE_CODE_TTL_MINUTES = 30


def generate_invite_code() -> str:
    return "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_LENGTH))


class FamilyInviteCode(Base):
    """가족 초대코드. 보호자가 발급하면, 그 코드를 아는 사람이 입력하는 즉시 연결된다
    (승인 절차 없음 - 코드를 전달받았다는 것 자체가 이미 상대방의 동의로 간주). 1회용이고
    유효시간(기본 30분)이 지나거나 이미 사용됐으면 재사용할 수 없다.
    """

    __tablename__ = "family_invite_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guardian_profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(INVITE_CODE_LENGTH), unique=True, nullable=False)
    relation_label: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def is_valid(self, now: datetime) -> bool:
        expires_at = self.expires_at
        # MySQL/SQLite 둘 다 DateTime(timezone=True)로 저장해도 읽어올 때 tzinfo가 없는
        # naive datetime으로 돌아오는 경우가 있다(로그인 잠금의 locked_until과 같은 문제 -
        # app/services/auth.py 참고). 그대로 비교하면 TypeError가 나므로 여기서 보정한다.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        return self.used_at is None and now < expires_at


def default_expiry(now: datetime) -> datetime:
    return now + timedelta(minutes=INVITE_CODE_TTL_MINUTES)
