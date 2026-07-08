"""
[T-AUTH-7 동의 순서 수정] 신규 소셜 가입자는 /callback에서 바로 계정이 생기지 않는다.
"약관동의+정보입력"에 해당하는 /complete-signup을 호출해야 비로소 User+Profile이 생긴다.
기존 사용자(재로그인, 이메일 연결)는 예전 그대로 콜백에서 바로 로그인 처리된다.
"""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.profiles import Profile
from app.models.users import User
from app.tests.conftest import TestSessionLocal

AGREEMENTS = {"service_terms": True, "privacy": True, "sensitive_info": True}

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
    """httpx.AsyncClient를 흉내낸 가짜 클라이언트. app.services.oauth 안에서만 이걸 쓰게 바꿔치기한다
    (테스트 자체가 쓰는 진짜 httpx.AsyncClient는 건드리지 않도록 범위를 좁힘)."""

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
        def AsyncClient(*args, **kwargs):  # noqa: N802 (httpx.AsyncClient 이름을 흉내내는 용도)
            return FakeAsyncClient(token_data, userinfo_data)

    return FakeHttpxModule


def _extract_pending_token(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    qs = parse_qs(parsed.query)
    assert "pending_token" in qs, f"pending_token이 리다이렉트 주소에 없음: {redirect_url}"
    return qs["pending_token"][0]


async def test_oauth_login_redirects_for_supported_providers():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for provider in ("google", "naver", "kakao"):
            response = await client.get(f"/api/v1/auth/{provider}/login", follow_redirects=False)
            assert response.status_code in (302, 307)


async def test_oauth_login_unsupported_provider():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/facebook/login", follow_redirects=False)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_new_social_user_does_not_create_account_at_callback():
    """[핵심] 신규 소셜 사용자는 콜백 시점엔 계정이 생기면 안 된다 - 아직 우리 약관에 동의 전이다."""
    for provider, fake in FAKE_RESPONSES.items():
        fake_module = make_fake_httpx_module(fake["token"], fake["userinfo"])
        with patch("app.services.oauth.httpx", new=fake_module):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(f"/api/v1/auth/{provider}/callback?code=fake_code", follow_redirects=False)

        assert response.status_code in (302, 307), f"{provider}: {response.status_code}"
        # 아직 가입 전이므로 refresh_token 쿠키가 있으면 안 된다
        assert not any("refresh_token" in h for h in response.headers.get_list("set-cookie"))
        # 대신 pending_token을 담아 /social-signup으로 보내야 한다
        assert "/social-signup" in response.headers["location"]
        _extract_pending_token(response.headers["location"])

        async with TestSessionLocal() as session:
            user = (
                await session.execute(select(User).where(User.sns_provider == provider.upper()))
            ).scalar_one_or_none()
            assert user is None, f"{provider}: 동의 전인데 계정이 이미 생겨버림"


async def test_complete_social_signup_creates_user_and_profile_and_issues_tokens():
    fake = FAKE_RESPONSES["google"]
    fake_module = make_fake_httpx_module(fake["token"], fake["userinfo"])
    with patch("app.services.oauth.httpx", new=fake_module):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            callback_response = await client.get("/api/v1/auth/google/callback?code=fake_code", follow_redirects=False)
    pending_token = _extract_pending_token(callback_response.headers["location"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/google/complete-signup",
            json={
                "pending_token": pending_token,
                "name": "구글유저",
                "gender": "MALE",
                "birth_date": "1995-05-05",
                "phone_number": "01099998888",
                "agreements": AGREEMENTS,
            },
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert "access_token" in response.json()
    assert "profile_id" in response.json()
    assert any("refresh_token" in h for h in response.headers.get_list("set-cookie"))

    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.sns_provider == "GOOGLE"))).scalar_one()
        assert user.sensitive_info_agreed_at is not None  # 민감정보 동의도 기록됐어야 함
        profile = (await session.execute(select(Profile).where(Profile.user_id == user.id))).scalar_one()
        assert profile.gender == "MALE"
        assert profile.phone_number == "01099998888"


async def test_complete_social_signup_rejects_missing_required_agreement():
    fake = FAKE_RESPONSES["naver"]
    fake_module = make_fake_httpx_module(fake["token"], fake["userinfo"])
    with patch("app.services.oauth.httpx", new=fake_module):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            callback_response = await client.get("/api/v1/auth/naver/callback?code=fake_code", follow_redirects=False)
    pending_token = _extract_pending_token(callback_response.headers["location"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/naver/complete-signup",
            json={
                "pending_token": pending_token,
                "name": "네이버유저",
                "gender": "FEMALE",
                "birth_date": "1995-05-05",
                "phone_number": "01011119999",
                "agreements": {"service_terms": True, "privacy": True, "sensitive_info": False},
            },
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_complete_social_signup_rejects_expired_or_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/google/complete-signup",
            json={
                "pending_token": "not-a-real-token",
                "name": "누구게",
                "gender": "MALE",
                "birth_date": "1995-05-05",
                "phone_number": "01000000000",
                "agreements": AGREEMENTS,
            },
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_callback_links_existing_local_account_by_email_without_consent_screen():
    """이메일이 같은 기존 로컬 계정이 있으면 - 이미 가입 때 동의했으므로 - 콜백에서 바로 로그인된다."""
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
                "agreements": AGREEMENTS,
            },
        )

    fake_module = make_fake_httpx_module(
        {"access_token": "fake"},
        {"sub": "google-linked-uid", "email": "linked@example.com", "name": "기존유저(구글)"},
    )
    with patch("app.services.oauth.httpx", new=fake_module):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/google/callback?code=xyz", follow_redirects=False)

    # 기존 계정 연결이므로 곧바로 로그인 처리(쿠키 발급)되어야 하고, /social-signup으로 새지 않아야 한다
    assert any("refresh_token" in h for h in response.headers.get_list("set-cookie"))
    assert "/social-signup" not in response.headers["location"]

    async with TestSessionLocal() as session:
        users = (await session.execute(select(User).where(User.email == "linked@example.com"))).scalars().all()
        assert len(users) == 1  # 같은 이메일로 새 계정이 또 생기면 안 됨
        assert users[0].sns_provider == "GOOGLE"

        # 기존 회원가입 때 만들어졌던 Profile을 그대로 재사용해야 하고(신규 생성 아님), 이름도 그대로 유지되어야 함
        profiles = (await session.execute(select(Profile).where(Profile.user_id == users[0].id))).scalars().all()
        assert len(profiles) == 1
        assert profiles[0].name == "기존유저"


async def test_existing_sns_user_relogin_skips_consent_screen():
    """이미 이 소셜계정으로 가입 완료된 사용자가 재로그인하면, 콜백에서 바로 토큰이 나와야 한다
    (매번 로그인할 때마다 동의 화면이 다시 뜨면 안 된다)."""
    fake = FAKE_RESPONSES["kakao"]
    fake_module = make_fake_httpx_module(fake["token"], fake["userinfo"])

    # 1차: 최초 가입 (콜백 -> complete-signup)
    with patch("app.services.oauth.httpx", new=fake_module):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_callback = await client.get("/api/v1/auth/kakao/callback?code=code1", follow_redirects=False)
    pending_token = _extract_pending_token(first_callback.headers["location"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/kakao/complete-signup",
            json={
                "pending_token": pending_token,
                "name": "카카오유저",
                "gender": "MALE",
                "birth_date": "1995-05-05",
                "phone_number": "01055554444",
                "agreements": AGREEMENTS,
            },
        )

    # 2차: 같은 사용자가 다시 로그인 -> 콜백에서 바로 토큰이 나와야 함
    with patch("app.services.oauth.httpx", new=fake_module):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            second_callback = await client.get("/api/v1/auth/kakao/callback?code=code2", follow_redirects=False)

    assert any("refresh_token" in h for h in second_callback.headers.get_list("set-cookie"))
    assert "/social-signup" not in second_callback.headers["location"]
