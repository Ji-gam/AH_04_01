"""
[T-AUTH-3] 로그아웃 실제 무효화 테스트.
로그아웃 자체(200)뿐 아니라, 로그아웃 "이후" 남아있는 refresh_token 쿠키로
재발급을 시도하면 반드시 401로 막혀야 한다 — 이게 이번 작업의 핵심 정의 조건이다.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "로그아웃테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01033334444",
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return response.json()["access_token"]


async def test_logout_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/logout")
    assert response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_logout_success_and_refresh_token_actually_invalidated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        access_token = await _signup_and_login(client, "logout_test@example.com")

        # 로그아웃 전: 재발급이 정상적으로 되어야 한다 (쿠키는 client가 자동으로 들고 있음)
        pre_logout_refresh = await client.get("/api/v1/auth/token/refresh")
        assert pre_logout_refresh.status_code == status.HTTP_200_OK

        # 로그아웃
        logout_response = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
        assert logout_response.status_code == status.HTTP_200_OK

        # [핵심] 로그아웃 후에는, 브라우저에 아직 남아있는(혹은 탈취된) 옛 refresh_token 쿠키로
        # 재발급을 시도해도 401로 막혀야 한다 — 서명은 유효해도 DB에서 이미 지워졌기 때문.
        post_logout_refresh = await client.get("/api/v1/auth/token/refresh")
        assert post_logout_refresh.status_code == status.HTTP_401_UNAUTHORIZED


async def test_logout_clears_refresh_token_cookie_in_response():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        access_token = await _signup_and_login(client, "logout_cookie_test@example.com")
        response = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "refresh_token=" in h and ("Max-Age=0" in h or "expires=Thu, 01-Jan-1970" in h) for h in set_cookie_headers
    )
