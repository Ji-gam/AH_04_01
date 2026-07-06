from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.users import User

# 구글/네이버/카카오가 실제로 돌려주는 형태를 흉내낸 가짜 응답들
FAKE_RESPONSES = {
    "google": {
        "token": {"access_token": "fake_google_token"},
        "userinfo": {"sub": "google-uid-123", "email": "gtest@gmail.com", "name": "구글유저"},
    },
    "naver": {
        "token": {"access_token": "fake_naver_token"},
        "userinfo": {"response": {"id": "naver-uid-456", "email": "ntest@naver.com", "name": "네이버유저"}},
    },
    "kakao": {
        "token": {"access_token": "fake_kakao_token"},
        "userinfo": {"id": 789, "kakao_account": {"email": "ktest@kakao.com", "profile": {"nickname": "카카오유저"}}},
    },
}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class FakeAsyncClient:
    """httpx.AsyncClient를 흉내낸 가짜 클라이언트. app.services.oauth 안에서만 이걸 쓰게 바꿔치기합니다
    (테스트 자체가 쓰는 진짜 httpx.AsyncClient는 절대 건드리지 않도록 범위를 좁힘)."""

    def __init__(self, token_data, userinfo_data):
        self._token_data = token_data
        self._userinfo_data = userinfo_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        return FakeResponse(self._token_data)

    async def get(self, url, **kwargs):
        return FakeResponse(self._userinfo_data)


def make_fake_httpx_module(token_data: dict, userinfo_data: dict):
    class FakeHttpxModule:
        @staticmethod
        def AsyncClient(*args, **kwargs):  # noqa: N802 (httpx.AsyncClient 이름을 그대로 흉내내는 용도)
            return FakeAsyncClient(token_data, userinfo_data)

    return FakeHttpxModule


class TestOAuthLoginStart(TestCase):
    async def test_oauth_login_redirects_for_supported_providers(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for provider in ("google", "naver", "kakao"):
                response = await client.get(f"/api/v1/auth/{provider}/login", follow_redirects=False)
                assert response.status_code in (302, 307)

    async def test_oauth_login_unsupported_provider(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/facebook/login", follow_redirects=False)
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestOAuthCallback(TestCase):
    async def test_callback_creates_user_and_issues_tokens(self):
        for provider, fake in FAKE_RESPONSES.items():
            fake_module = make_fake_httpx_module(fake["token"], fake["userinfo"])
            with patch("app.services.oauth.httpx", new=fake_module):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get(
                        f"/api/v1/auth/{provider}/callback?code=fake_code", follow_redirects=False
                    )

            assert response.status_code in (302, 307), f"{provider}: {response.status_code}"
            assert any("refresh_token" in header for header in response.headers.get_list("set-cookie"))

            user = await User.get_or_none(sns_provider=provider.upper())
            assert user is not None

    async def test_callback_links_existing_local_account_by_email(self):
        # 먼저 이메일 가입
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "linked@example.com",
                    "password": "Password123!",
                    "name": "기존유저",
                    "gender": "MALE",
                    "birth_date": "1990-01-01",
                    "phone_number": "01012341234",
                    "agreed_terms": True,
                },
            )

        fake_module = make_fake_httpx_module(
            {"access_token": "fake"},
            {"sub": "google-linked-uid", "email": "linked@example.com", "name": "기존유저(구글)"},
        )
        with patch("app.services.oauth.httpx", new=fake_module):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                await client.get("/api/v1/auth/google/callback?code=xyz", follow_redirects=False)

        users = await User.filter(email="linked@example.com").all()
        assert len(users) == 1  # 같은 이메일로 새 계정이 또 생기면 안 됨 (기존 계정에 연결되어야 함)
        assert users[0].sns_provider == "GOOGLE"
