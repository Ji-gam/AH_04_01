from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.utils.common import normalize_phone_number
from app.dtos.users import ConsentUpdateRequest, UserUpdateRequest
from app.models.profiles import Profile
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.services.auth import AuthService


class UserManageService:
    def __init__(self):
        self.profile_repo = ProfileRepository()
        self.auth_service = AuthService()

    async def update_user(
        self, session: AsyncSession, user: User, profile: Profile, data: UserUpdateRequest
    ) -> tuple[User, Profile]:
        if data.phone_number:
            normalized_phone_number = normalize_phone_number(data.phone_number)
            await self.auth_service.check_phone_number_exists(session, normalized_phone_number)
            data.phone_number = normalized_phone_number

        profile_fields = data.model_dump(exclude_none=True)
        await self.profile_repo.update_instance(session, profile, profile_fields)
        await session.commit()
        return user, profile

    async def update_consent(self, session: AsyncSession, user: User, data: ConsentUpdateRequest) -> User:
        """[개인정보보호법 제23조 등] true를 보내면 그 시각으로 갱신한다 - false/미전달은 기존
        상태(동의 안 함, 또는 이미 동의한 시각)를 그대로 둔다. 필수 3종(이용약관/건강정보/
        AI챗봇)은 명시적으로 철회하는 기능을 여기서 다루지 않는다(회원탈퇴 시 계정 자체가
        삭제되므로 별도 철회 API는 불필요). 마케팅(선택)은 유일하게 껐다 켤 수 있는데, 그건
        이 메서드가 아니라 set_marketing_consent가 전담한다 - 둘을 같은 메서드에 섞으면
        나중에 필수 항목까지 실수로 철회 가능하게 만들 위험이 있어 아예 분리했다."""
        now = datetime.now(tz=config.TIMEZONE)
        if data.health_info:
            user.health_info_consented_at = now
        if data.ai_chat:
            user.ai_chat_consented_at = now
        if data.terms_of_service:
            user.terms_of_service_consented_at = now
        if data.marketing:
            user.marketing_consented_at = now
        await session.commit()
        return user

    async def set_marketing_consent(self, session: AsyncSession, user: User, enabled: bool) -> User:
        """(2026-07-30) "내 동의 현황" 화면에서 마케팅 동의만 토글로 껐다 켤 수 있게
        지원한다 - 필수 3종은 회원탈퇴 외에는 철회 방법이 없지만, 마케팅은 선택 항목이라
        법적으로도 언제든 철회 가능해야 한다.
        - 켜면: marketing_consented_at을 지금 시각으로 갱신 + revoked_at은 초기화(null)
        - 끄면: marketing_consented_at은 "최초 동의했던 기록"으로 그대로 두고,
          marketing_consent_revoked_at에 지금 시각만 남긴다 - 관리자 화면에서
          "언제 동의했다가 언제 취소했는지" 둘 다 보이게 하기 위함."""
        now = datetime.now(tz=config.TIMEZONE)
        if enabled:
            user.marketing_consented_at = now
            user.marketing_consent_revoked_at = None
        else:
            user.marketing_consent_revoked_at = now
        await session.commit()
        return user
