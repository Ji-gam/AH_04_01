"""
[T-AUTH-8] 회원탈퇴 테스트.
LOCAL 계정은 비밀번호 재확인 필수, 소셜 계정은 비밀번호 없이도 탈퇴 가능해야 한다.
탈퇴 후엔 User/Profile이 실제로 삭제되고, 같은 이메일/전화번호로 재가입도 가능해야 한다.
"""

from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.profiles import Profile
from app.models.users import User
from app.tests.conftest import TestSessionLocal

AGREEMENTS = {"service_terms": True, "privacy": True, "sensitive_info": True}


async def _signup_login_and_get_token(client: AsyncClient, email: str, password: str = "Password123!") -> str:
    signup_data = {
        "email": email,
        "password": password,
        "name": "탈퇴테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01077778888",
        "agreements": AGREEMENTS,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_response.json()["access_token"]


async def test_withdraw_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request("DELETE", "/api/v1/auth/withdraw", json={"password": "x"})
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_local_account_withdraw_rejects_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "withdraw_wrong_pw@example.com")
        response = await client.request(
            "DELETE",
            "/api/v1/auth/withdraw",
            json={"password": "WrongPassword!"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_local_account_withdraw_rejects_missing_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "withdraw_no_pw@example.com")
        response = await client.request(
            "DELETE", "/api/v1/auth/withdraw", json={}, headers={"Authorization": f"Bearer {token}"}
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_local_account_withdraw_success_deletes_user_and_profile():
    email = "withdraw_success@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, email)

        async with TestSessionLocal() as session:
            user_before = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user_id = user_before.id

        response = await client.request(
            "DELETE",
            "/api/v1/auth/withdraw",
            json={"password": "Password123!"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == status.HTTP_200_OK

    async with TestSessionLocal() as session:
        user_after = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        assert user_after is None  # User가 실제로 삭제되어야 함

        profile_after = (await session.execute(select(Profile).where(Profile.user_id == user_id))).scalar_one_or_none()
        assert profile_after is None  # cascade로 Profile도 같이 삭제되어야 함


async def test_withdraw_frees_up_email_and_phone_for_resignup():
    email = "withdraw_reuse@example.com"
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "재가입테스터",
        "gender": "FEMALE",
        "birth_date": "1990-01-01",
        "phone_number": "01099990001",
        "agreements": AGREEMENTS,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        token = login_response.json()["access_token"]

        await client.request(
            "DELETE",
            "/api/v1/auth/withdraw",
            json={"password": "Password123!"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # 탈퇴 직후, 같은 이메일/전화번호로 재가입이 되어야 한다 (중복 체크에 안 걸려야 함)
        resignup_response = await client.post("/api/v1/auth/signup", json=signup_data)
    assert resignup_response.status_code == status.HTTP_201_CREATED


async def test_social_account_withdraw_without_password():
    """소셜 가입자는 비밀번호가 없으므로, 인증된 토큰만으로 탈퇴가 되어야 한다."""
    fake_userinfo = {"sub": "google-withdraw-uid", "email": "social_withdraw@example.com", "name": "소셜탈퇴테스터"}

    class FakeResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            return FakeResponse({"access_token": "fake"})

        async def get(self, url, **kwargs):
            return FakeResponse(fake_userinfo)

    class FakeHttpxModule:
        @staticmethod
        def AsyncClient(*args, **kwargs):  # noqa: N802 (httpx.AsyncClient 이름을 흉내내는 용도)
            return FakeAsyncClient()

    with patch("app.services.oauth.httpx", new=FakeHttpxModule):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            callback_response = await client.get("/api/v1/auth/google/callback?code=x", follow_redirects=False)
            from urllib.parse import parse_qs, urlparse

            qs = parse_qs(urlparse(callback_response.headers["location"]).query)
            pending_token = qs["pending_token"][0]

            complete_response = await client.post(
                "/api/v1/auth/google/complete-signup",
                json={
                    "pending_token": pending_token,
                    "name": "소셜탈퇴테스터",
                    "gender": "MALE",
                    "birth_date": "1995-05-05",
                    "phone_number": "01066667777",
                    "agreements": AGREEMENTS,
                },
            )
            token = complete_response.json()["access_token"]

            withdraw_response = await client.request(
                "DELETE", "/api/v1/auth/withdraw", json={}, headers={"Authorization": f"Bearer {token}"}
            )
    assert withdraw_response.status_code == status.HTTP_200_OK

    async with TestSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == "social_withdraw@example.com"))
        ).scalar_one_or_none()
        assert user is None
