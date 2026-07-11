from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.core import config
from app.main import app
from app.models.users import User
from app.services.oauth_clients import SocialUserInfo
from app.tests.conftest import TestSessionLocal


async def test_social_login_redirects_to_google():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
        response = await client.get("/api/v1/auth/google/login")
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].startswith("https://accounts.google.com/")


async def test_social_login_unsupported_provider_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/apple/login")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_google_callback_new_user_creates_account_immediately_and_logs_in():
    # [단순화] 동의/추가정보 화면 없이, 콜백 한 번에 계정 생성 + 로그인까지 끝난다.
    fake_userinfo = SocialUserInfo(sns_id="google-sub-new-1", email="newgoogleuser@example.com", name="구글신규닉네임")
    with patch(
        "app.services.oauth_clients.GoogleOAuthClient.fetch_userinfo", new=AsyncMock(return_value=fake_userinfo)
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            response = await client.get("/api/v1/auth/google/callback", params={"code": "fake-code"})

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == f"{config.FRONTEND_URL}/"
    assert "refresh_token" in response.headers.get("set-cookie", "")

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "newgoogleuser@example.com"))).scalar_one()
        assert user.sns_provider == "google"
        assert user.sns_id == "google-sub-new-1"
        assert user.hashed_password is None  # 소셜 가입자는 비밀번호가 없어야 한다


async def test_google_callback_existing_user_logs_in():
    fake_userinfo = SocialUserInfo(
        sns_id="google-sub-existing-1", email="existinggoogleuser@example.com", name="구글기존"
    )
    with patch(
        "app.services.oauth_clients.GoogleOAuthClient.fetch_userinfo", new=AsyncMock(return_value=fake_userinfo)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/api/v1/auth/google/callback", params={"code": "fake-code-1"})

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            response = await client.get("/api/v1/auth/google/callback", params={"code": "fake-code-2"})

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == f"{config.FRONTEND_URL}/"
    assert "refresh_token" in response.headers.get("set-cookie", "")

    # 두 번째 콜백에서 새 계정이 또 생기면 안 된다 - 여전히 하나만 있어야 한다
    async with TestSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "existinggoogleuser@example.com"))
        assert len(result.scalars().all()) == 1


async def test_google_callback_email_already_used_by_local_account():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "alreadylocal@example.com", "password": "password123!", "name": "로컬유저"},
        )

    fake_userinfo = SocialUserInfo(sns_id="google-sub-conflict-1", email="alreadylocal@example.com", name="구글충돌")
    with patch(
        "app.services.oauth_clients.GoogleOAuthClient.fetch_userinfo", new=AsyncMock(return_value=fake_userinfo)
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/google/callback", params={"code": "fake-code-3"})

    assert response.status_code == status.HTTP_409_CONFLICT


async def test_kakao_login_redirects_to_kakao():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
        response = await client.get("/api/v1/auth/kakao/login")
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].startswith("https://kauth.kakao.com/")


async def test_kakao_callback_new_user_uses_temp_email():
    # 카카오는 이메일 동의항목이 없는 게 흔한 케이스 - kakao_account에 email 자체가 없다.
    fake_userinfo = SocialUserInfo(
        sns_id="kakao-sub-1", email="kakao_kakao-sub-1@social.local", name="카카오신규닉네임"
    )
    with patch("app.services.oauth_clients.KakaoOAuthClient.fetch_userinfo", new=AsyncMock(return_value=fake_userinfo)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            response = await client.get("/api/v1/auth/kakao/callback", params={"code": "fake-kakao-code"})

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "refresh_token" in response.headers.get("set-cookie", "")

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "kakao_kakao-sub-1@social.local"))).scalar_one()
        assert user.sns_provider == "kakao"
        assert user.hashed_password is None


async def test_naver_login_redirects_to_naver():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as client:
        response = await client.get("/api/v1/auth/naver/login")
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"].startswith("https://nid.naver.com/")


async def test_naver_callback_new_user_creates_account():
    fake_userinfo = SocialUserInfo(sns_id="naver-sub-1", email="naveruser@example.com", name="네이버닉네임")
    with patch("app.services.oauth_clients.NaverOAuthClient.fetch_userinfo", new=AsyncMock(return_value=fake_userinfo)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
        ) as client:
            response = await client.get("/api/v1/auth/naver/callback", params={"code": "fake-naver-code"})

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert "refresh_token" in response.headers.get("set-cookie", "")

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == "naveruser@example.com"))).scalar_one()
        assert user.sns_provider == "naver"
        assert user.hashed_password is None
