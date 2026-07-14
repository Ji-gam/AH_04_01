from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.models.profiles import ProfileRelation
from app.repositories.profile_repository import ProfileRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService
from app.services.oauth_clients import SocialUserInfo


class SocialAuthService:
    """소셜 로그인 콜백 처리.

    [단순화] 일반 회원가입도 이제 닉네임+이메일+비밀번호만 받는다 - 소셜 로그인은 provider가
    이메일+이름(닉네임)을 이미 다 주기 때문에, 비밀번호 없이 그 정보만으로 곧바로 계정을 만들 수
    있다. 그래서 예전처럼 "동의 -> 추가정보 입력 -> 계정생성" 중간 단계 없이, 콜백 한 번에
    기존 계정 로그인 또는 신규 계정 생성까지 끝낸다. 나이/성별/건강정보는 원래부터 회원가입과
    무관하게 더보기 > 개인건강정보에서 받으므로 여기서도 그대로 그 흐름을 그대로 탄다.
    """

    def __init__(self):
        self.user_repo = UserRepository()
        self.profile_repo = ProfileRepository()
        self.refresh_token_repo = RefreshTokenRepository()
        self.jwt_service = JwtService()

    async def handle_callback(
        self, session: AsyncSession, provider: str, userinfo: SocialUserInfo
    ) -> dict[str, AccessToken | RefreshToken]:
        user = await self.user_repo.get_by_sns(session, provider, userinfo.sns_id)

        if user is None:
            # 신규 - 이메일이 이미 다른 방식(로컬 가입 또는 다른 provider)으로 쓰이고 있으면 막는다.
            # (계정 자동 연결은 아직 지원 안 함 - 다음 단계에서 다룬다)
            if await self.user_repo.exists_by_email(session, userinfo.email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 이 이메일로 가입된 계정이 있습니다. 이메일로 로그인해주세요.",
                )
            user = await self.user_repo.create_social_user(
                session, email=userinfo.email, sns_provider=provider, sns_id=userinfo.sns_id
            )
            profile = await self.profile_repo.create_profile(
                session, user_id=user.id, name=userinfo.name, relation=ProfileRelation.SELF
            )
        else:
            profile = await self.profile_repo.get_default_profile_for_user(session, user.id)
            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다."
                )

        await self.user_repo.update_last_login(session, user.id)
        tokens = self.jwt_service.issue_jwt_pair(user, profile)
        # [리프레시 토큰 로테이션] 이메일 로그인과 동일하게, 발급한 리프레시 토큰의 jti를 추적한다.
        refresh_token = tokens["refresh_token"]
        await self.refresh_token_repo.create(session, user.id, refresh_token.payload["jti"])
        await session.commit()
        return tokens
