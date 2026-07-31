"""소셜 로그인 provider별 OAuth 클라이언트.

이름칸은 프로젝트 전체에서 "닉네임"으로 취급하기로 했다 - 그래서 provider가 실명/닉네임을
둘 다 주는 경우(네이버)는 닉네임 쪽을 우선한다.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

import httpx

from app.core import config


@dataclass
class SocialUserInfo:
    sns_id: str
    email: str
    name: str  # 실제로는 "닉네임"으로 취급 - 회원가입의 name(닉네임) 필드와 동일하게 저장된다.


class OAuthClient(Protocol):
    def get_authorize_url(self) -> str: ...

    async def fetch_userinfo(self, code: str) -> SocialUserInfo: ...


class GoogleOAuthClient:
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"  # noqa: S105 (비밀값 아니라 공개 엔드포인트 URL)
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    def get_authorize_url(self) -> str:
        params = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
        }
        return str(httpx.URL(self.authorize_url, params=params))

    async def fetch_userinfo(self, code: str) -> SocialUserInfo:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                self.token_url,
                data={
                    "code": code,
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": config.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = await client.get(self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            userinfo_response.raise_for_status()
            data = userinfo_response.json()

        # 구글의 "name"은 구글 계정 표시이름(실명일 수도, 닉네임일 수도 있음) - 그대로 우리 쪽 닉네임으로 쓴다.
        return SocialUserInfo(
            sns_id=data["sub"],
            email=data["email"],
            name=data.get("name") or data.get("given_name") or "구글사용자",
        )


def parse_kakao_userinfo(data: dict) -> SocialUserInfo:
    """카카오 /v2/user/me 응답을 SocialUserInfo로 변환하는 순수 함수 (네트워크 없이 단위테스트 가능).

    TODO(비즈앱 신청 후): 지금은 비즈앱 전환 전이라 kakao_account.email이 대부분 안 온다.
    이메일이 오면 그 값을 그대로 쓰고, 안 오면 sns_id 기반 임시 이메일로 채워서 가입 자체는 막지 않는다.
    비즈앱 신청 완료되면, 이 임시 이메일 생성 로직만 지우고 실제 이메일을 필수로 받게 바꾸면 된다.
    """
    kakao_account = data.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    sns_id = str(data["id"])

    email = kakao_account.get("email")
    if not email:
        email = f"kakao_{sns_id}@social.local"

    # 카카오는 필드 이름 자체가 "nickname"이라 우리 쪽 닉네임 개념이랑 그대로 일치한다.
    name = profile.get("nickname") or "카카오사용자"

    return SocialUserInfo(sns_id=sns_id, email=email, name=name)


class KakaoOAuthClient:
    authorize_url = "https://kauth.kakao.com/oauth/authorize"
    token_url = "https://kauth.kakao.com/oauth/token"  # noqa: S105 (비밀값 아니라 공개 엔드포인트 URL)
    userinfo_url = "https://kapi.kakao.com/v2/user/me"

    def get_authorize_url(self) -> str:
        params = {
            "client_id": config.KAKAO_CLIENT_ID,
            "redirect_uri": config.KAKAO_REDIRECT_URI,
            "response_type": "code",
        }
        return str(httpx.URL(self.authorize_url, params=params))

    async def fetch_userinfo(self, code: str) -> SocialUserInfo:
        async with httpx.AsyncClient() as client:
            token_data = {
                "grant_type": "authorization_code",
                "client_id": config.KAKAO_CLIENT_ID,
                "redirect_uri": config.KAKAO_REDIRECT_URI,
                "code": code,
            }
            if config.KAKAO_CLIENT_SECRET:
                token_data["client_secret"] = config.KAKAO_CLIENT_SECRET

            token_response = await client.post(self.token_url, data=token_data)
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = await client.get(self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            userinfo_response.raise_for_status()
            data = userinfo_response.json()

        return parse_kakao_userinfo(data)


def parse_naver_userinfo(data: dict) -> SocialUserInfo:
    """네이버 /v1/nid/me 응답을 SocialUserInfo로 변환하는 순수 함수 (네트워크 없이 단위테스트 가능).

    네이버는 실명(name)과 닉네임(nickname)을 따로 준다 - "이름칸=닉네임" 원칙에 맞춰
    nickname을 우선 쓰고, 닉네임 동의항목을 안 받았거나 값이 없으면 실명으로 대체한다.
    """
    response = data["response"]
    name = response.get("nickname") or response.get("name") or "네이버사용자"
    return SocialUserInfo(sns_id=response["id"], email=response["email"], name=name)


class NaverOAuthClient:
    authorize_url = "https://nid.naver.com/oauth2.0/authorize"
    token_url = "https://nid.naver.com/oauth2.0/token"  # noqa: S105 (비밀값 아니라 공개 엔드포인트 URL)
    userinfo_url = "https://openapi.naver.com/v1/nid/me"

    def get_authorize_url(self) -> str:
        # 네이버는 CSRF 방지용 state 파라미터를 필수로 요구한다. 지금은 매 요청마다 무작위 값만 채워서
        # "필수값 없음" 오류를 막는 수준이고, 콜백에서 되돌아온 state를 검증하는 로직은 아직 없다(TODO).
        params = {
            "response_type": "code",
            "client_id": config.NAVER_CLIENT_ID,
            "redirect_uri": config.NAVER_REDIRECT_URI,
            "state": uuid4().hex,
        }
        return str(httpx.URL(self.authorize_url, params=params))

    async def fetch_userinfo(self, code: str) -> SocialUserInfo:
        async with httpx.AsyncClient() as client:
            token_response = await client.get(
                self.token_url,
                params={
                    "grant_type": "authorization_code",
                    "client_id": config.NAVER_CLIENT_ID,
                    "client_secret": config.NAVER_CLIENT_SECRET,
                    "code": code,
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]

            userinfo_response = await client.get(self.userinfo_url, headers={"Authorization": f"Bearer {access_token}"})
            userinfo_response.raise_for_status()
            data = userinfo_response.json()

        return parse_naver_userinfo(data)


_CLIENTS: dict[str, OAuthClient] = {
    "google": GoogleOAuthClient(),
    "kakao": KakaoOAuthClient(),
    "naver": NaverOAuthClient(),
}


def get_oauth_client(provider: str) -> OAuthClient:
    client = _CLIENTS.get(provider)
    if client is None:
        raise ValueError(f"지원하지 않는 provider: {provider}")
    return client


def supported_providers() -> list[str]:
    return list(_CLIENTS.keys())
