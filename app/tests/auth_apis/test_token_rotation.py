"""
[T-AUTH-5] Refresh Token 회전(rotation) 테스트.
재발급할 때마다 refresh_token 자체도 새로 바뀌어야 하고, 한 번 쓰인 예전 refresh_token은
그 즉시 재사용이 막혀야 한다 - 이게 이번 작업의 핵심 정의 조건이다 (탈취 대비).
"""

import re

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


def _extract_refresh_token(set_cookie_header: str | None) -> str:
    assert set_cookie_header is not None
    match = re.search(r"refresh_token=([^;]+)", set_cookie_header)
    assert match is not None
    return match.group(1)


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "회전테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01055556666",
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return _extract_refresh_token(login_response.headers.get("set-cookie"))


async def test_refresh_issues_a_brand_new_refresh_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        old_refresh_token = await _signup_and_login(client, "rotation_new_token@example.com")
        client.cookies["refresh_token"] = old_refresh_token

        response = await client.get("/api/v1/auth/token/refresh")
        new_refresh_token = _extract_refresh_token(response.headers.get("set-cookie"))

    assert response.status_code == status.HTTP_200_OK
    assert new_refresh_token != old_refresh_token, "재발급 후에도 refresh_token 값이 그대로다 (회전 안 됨)"


async def test_old_refresh_token_cannot_be_reused_after_rotation():
    """[핵심] 정상 사용자가 재발급을 한 번 받으면, 그 순간 예전 refresh_token은 (설령 누군가
    탈취해서 들고 있었더라도) 더 이상 재발급에 쓸 수 없어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        old_refresh_token = await _signup_and_login(client, "rotation_reuse@example.com")

        client.cookies["refresh_token"] = old_refresh_token
        first_refresh = await client.get("/api/v1/auth/token/refresh")
        assert first_refresh.status_code == status.HTTP_200_OK
        new_refresh_token = _extract_refresh_token(first_refresh.headers.get("set-cookie"))
        assert new_refresh_token != old_refresh_token

        # 도둑(또는 새로고침 중복 요청)이 "예전" 토큰으로 다시 시도 -> 반드시 실패해야 한다
        client.cookies["refresh_token"] = old_refresh_token
        replay_attempt = await client.get("/api/v1/auth/token/refresh")
        assert replay_attempt.status_code == status.HTTP_401_UNAUTHORIZED

        # 새로 받은 토큰으로는 정상적으로 계속 재발급이 되어야 한다
        client.cookies["refresh_token"] = new_refresh_token
        legit_retry = await client.get("/api/v1/auth/token/refresh")
        assert legit_retry.status_code == status.HTTP_200_OK
