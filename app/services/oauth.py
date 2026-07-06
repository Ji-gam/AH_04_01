# app/services/oauth.py
# [핀포인트 추가] 구글/네이버/카카오 소셜 로그인 처리 서비스
import secrets

import httpx
from fastapi import HTTPException
from starlette import status

from app.core import config
from app.core.oauth.providers import get_provider_config, normalize_userinfo
from app.core.utils.security import hash_password
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService


class OAuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.jwt_service = JwtService()

    def build_authorize_url(self, provider: str) -> str:
        cfg = get_provider_config(provider)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 로그인 제공자입니다: {provider}"
            )

        redirect_uri = f"{config.BACKEND_BASE_URL}/api/v1/auth/{provider}/callback"
        params = {"client_id": cfg["client_id"], "redirect_uri": redirect_uri, "response_type": "code"}
        if cfg["scope"]:
            params["scope"] = cfg["scope"]

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cfg['authorize_url']}?{query}"

    async def handle_callback(self, provider: str, code: str) -> User:
        cfg = get_provider_config(provider)
        if not cfg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 로그인 제공자입니다: {provider}"
            )

        redirect_uri = f"{config.BACKEND_BASE_URL}/api/v1/auth/{provider}/callback"

        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": redirect_uri,
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

        profile = normalize_userinfo(provider, raw_userinfo)
        sns_id = profile.get("sns_id")
        email = profile.get("email")
        name = profile.get("name")

        if not sns_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{provider}에서 사용자 식별값을 받아오지 못했습니다."
            )

        provider_upper = provider.upper()

        # 1순위: 이미 이 소셜 계정으로 가입된 사용자인지 확인
        user = await self.user_repo.get_by_sns(provider_upper, str(sns_id))
        if user:
            return user

        # 2순위: 이메일이 같은 로컬 가입 계정이 있으면 그 계정에 소셜 정보만 연결
        if email:
            existing = await self.user_repo.get_user_by_email(email)
            if existing:
                await self.user_repo.link_sns_to_existing_user(existing, provider_upper, str(sns_id))
                return existing

        # 3순위: 완전 신규 가입 (본인만 아는 비밀번호가 없으니, 로그인 불가능한 랜덤값을 해시해서 채움)
        unusable_password = hash_password(secrets.token_urlsafe(32))
        new_user = await self.user_repo.create_social_user(
            email=email or f"{provider}_{sns_id}@social.remedi.local",
            hashed_password=unusable_password,
            name=name or f"{provider} 사용자",
            provider=provider_upper,
            sns_id=str(sns_id),
        )
        return new_user

    async def issue_tokens_for_social_login(self, user: User):
        """일반 로그인과 완전히 동일한 토큰 발급 절차를 재사용합니다."""
        await self.user_repo.update_last_login(user.id)
        tokens = self.jwt_service.issue_jwt_pair(user)
        await self.user_repo.update_refresh_token(user.id, str(tokens["refresh_token"]))
        return tokens
