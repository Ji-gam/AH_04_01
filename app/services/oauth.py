# app/services/oauth.py
# 구글/네이버/카카오 소셜 로그인 처리 서비스.
#
# [T-AUTH-7 동의 순서 수정] 개인정보보호법 제23조("동의 먼저, 처리는 그다음")를 지키기 위해,
# 콜백 시점에 사용자가 신규 가입자라면 여기서 바로 User/Profile을 만들지 않는다. 대신
# 제공자가 준 이름/이메일만 임시 서명 토큰(PendingSocialSignupToken)에 담아 프론트로 넘기고,
# 프론트가 "약관 동의 + 나머지 정보 입력" 화면을 거쳐 complete_social_signup()을 호출한
# 순간에만 실제로 계정이 생성된다. 이미 가입된 사용자(기존 SNS 연결/이메일 일치)는 예전에
# 이미 동의를 마쳤으므로 이 대기 단계 없이 바로 로그인 처리한다.
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.jwt.tokens import AccessToken, PendingSocialSignupToken, RefreshToken
from app.core.oauth.providers import get_provider_config, normalize_userinfo
from app.core.utils.common import normalize_phone_number
from app.core.utils.security import hash_password
from app.dtos.auth import AgreementRequest
from app.models.profiles import Gender, Profile, ProfileRelation
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService


@dataclass
class OAuthCallbackResult:
    """콜백 처리 결과. is_new_signup이 True면 계정이 아직 안 만들어진 상태이고,
    False면 (기존 사용자라) 토큰까지 이미 발급 완료된 상태다."""

    is_new_signup: bool
    # is_new_signup=False일 때만 채워짐
    tokens: dict[str, AccessToken | RefreshToken] | None = None
    # is_new_signup=True일 때만 채워짐
    pending_token: PendingSocialSignupToken | None = None
    provider: str | None = None
    email: str | None = None
    name: str | None = None


class OAuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.profile_repo = ProfileRepository()
        self.jwt_service = JwtService()

    def build_authorize_url(self, provider: str) -> str:
        cfg = get_provider_config(provider)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 로그인 제공자입니다: {provider}"
            )

        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "response_type": "code",
        }
        if cfg["scope"]:
            params["scope"] = cfg["scope"]

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cfg['authorize_url']}?{query}"

    async def handle_callback(self, session: AsyncSession, provider: str, code: str) -> OAuthCallbackResult:
        cfg = get_provider_config(provider)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 로그인 제공자입니다: {provider}"
            )

        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": cfg["redirect_uri"],
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_res.json()
            provider_access_token = token_data.get("access_token")
            if not provider_access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider} 토큰 발급에 실패했습니다: {token_data}"
                )

            userinfo_res = await client.get(
                cfg["userinfo_url"], headers={"Authorization": f"Bearer {provider_access_token}"}
            )
            raw_userinfo = userinfo_res.json()

        # [최소수집] 이름/이메일/식별자 외에는 애초에 요청도, 파싱도 안 한다 (providers.py 참고).
        profile_info = normalize_userinfo(provider, raw_userinfo)
        sns_id = profile_info.get("sns_id")
        email = profile_info.get("email")
        name = profile_info.get("name")

        if not sns_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider}에서 사용자 식별값을 받아오지 못했습니다."
            )

        provider_upper = provider.upper()

        # 1순위: 이미 이 소셜 계정으로 가입된 사용자 -> 예전에 이미 동의했으므로 바로 로그인
        user = await self.user_repo.get_by_sns(session, provider_upper, str(sns_id))
        if user:
            profile = await self.profile_repo.get_default_profile_for_user(session, user.id)
            if profile is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다."
                )
            tokens = await self._issue_tokens(session, user, profile)
            return OAuthCallbackResult(is_new_signup=False, tokens=tokens)

        # 2순위: 이메일이 같은 로컬 가입 계정이 있으면 연결 -> 이것도 원가입 때 이미 동의했으므로 바로 로그인
        if email:
            existing = await self.user_repo.get_user_by_email(session, email)
            if existing:
                await self.user_repo.link_sns_to_existing_user(session, existing, provider_upper, str(sns_id))
                profile = await self.profile_repo.get_default_profile_for_user(session, existing.id)
                if profile is None:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다."
                    )
                tokens = await self._issue_tokens(session, existing, profile)
                return OAuthCallbackResult(is_new_signup=False, tokens=tokens)

        # 3순위: 완전 신규 -> 여기서 계정을 만들지 않는다. 프론트의 "약관동의+정보입력" 화면을
        # 거쳐야만(complete_social_signup) 실제로 생성된다.
        pending_token = PendingSocialSignupToken.for_social_profile(
            provider=provider_upper, sns_id=str(sns_id), email=email, name=name
        )
        return OAuthCallbackResult(
            is_new_signup=True, pending_token=pending_token, provider=provider_upper, email=email, name=name
        )

    async def complete_social_signup(
        self,
        session: AsyncSession,
        pending_token: str,
        name: str,
        gender: Gender,
        birth_date: date,
        phone_number: str,
        agreements: AgreementRequest,
    ) -> dict[str, AccessToken | RefreshToken]:
        """[T-AUTH-7] 약관 동의 + 정보 입력 화면에서 호출된다. 이 시점에 비로소 계정을 만든다."""
        verified = self.jwt_service.verify_pending_social_signup(pending_token)
        provider = verified.payload["provider"]
        sns_id = verified.payload["sns_id"]
        email = verified.payload.get("email")

        # 이 사이(콜백~완료 화면) 동안 같은 소셜계정으로 중복 완료 요청이 왔을 수 있으니 다시 확인한다.
        existing_by_sns = await self.user_repo.get_by_sns(session, provider, sns_id)
        if existing_by_sns:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="이미 가입이 완료된 계정입니다. 로그인해주세요."
            )

        normalized_phone_number = normalize_phone_number(phone_number)
        if await self.profile_repo.exists_by_phone_number(session, normalized_phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")

        final_email = email or f"{provider.lower()}_{sns_id}@social.remedi.local"
        if await self.user_repo.exists_by_email(session, final_email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

        now = datetime.now(UTC)
        unusable_password = hash_password(secrets.token_urlsafe(32))
        new_user = await self.user_repo.create_social_user(
            session,
            email=final_email,
            hashed_password=unusable_password,
            provider=provider,
            sns_id=sns_id,
            service_terms_agreed_at=now,
            privacy_agreed_at=now,
            sensitive_info_agreed_at=now,
            marketing_agreed_at=now if agreements.marketing else None,
        )
        new_profile = await self.profile_repo.create_profile(
            session,
            user_id=new_user.id,
            name=name,
            phone_number=normalized_phone_number,
            gender=gender,
            birthday=birth_date,
            relation=ProfileRelation.SELF,
        )
        await session.commit()

        return await self._issue_tokens(session, new_user, new_profile)

    async def _issue_tokens(
        self, session: AsyncSession, user: User, profile: Profile
    ) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(session, user.id)
        tokens = self.jwt_service.issue_jwt_pair(user, profile)
        await self.user_repo.update_refresh_token(session, user.id, str(tokens["refresh_token"]))
        await session.commit()
        return tokens
