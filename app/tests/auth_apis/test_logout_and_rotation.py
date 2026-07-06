import re

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app


def _extract_refresh_token(response) -> str:
    set_cookie = response.headers.get("set-cookie")
    if not set_cookie:
        return ""
    match = re.search(r"refresh_token=([^;]+)", set_cookie)
    return match.group(1) if match else ""


class TestRefreshTokenRotation(TestCase):
    """[핀포인트 추가] 토큰 재발급 시 refresh_token도 같이 회전되고,
    회전 전 옛날 토큰은 더 이상 쓸 수 없어야 합니다 (탈취 대비 핵심 로직)."""

    async def test_refresh_token_rotates_and_old_one_is_invalidated(self):
        signup_data = {
            "email": "rotate@example.com",
            "password": "Password123!",
            "name": "회전테스터",
            "gender": "MALE",
            "birth_date": "1990-01-01",
            "phone_number": "01055556666",
            "agreed_terms": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": "rotate@example.com", "password": "Password123!"}
            )
            old_refresh_token = _extract_refresh_token(login_response)

            # 1차 갱신: 성공해야 하고, 새 refresh_token은 이전과 달라야 함
            client.cookies["refresh_token"] = old_refresh_token
            first_refresh_response = await client.get("/api/v1/auth/token/refresh")
            new_refresh_token = _extract_refresh_token(first_refresh_response)

            assert first_refresh_response.status_code == status.HTTP_200_OK
            assert new_refresh_token != ""
            assert new_refresh_token != old_refresh_token

            # 2차: 이미 회전되어 무효화된 "옛날" 토큰으로 다시 시도하면 401이어야 함
            client.cookies["refresh_token"] = old_refresh_token
            reuse_response = await client.get("/api/v1/auth/token/refresh")
            assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED

            # 3차: 새로 회전된 토큰으로는 정상적으로 갱신되어야 함
            client.cookies["refresh_token"] = new_refresh_token
            second_refresh_response = await client.get("/api/v1/auth/token/refresh")
            assert second_refresh_response.status_code == status.HTTP_200_OK


class TestLogout(TestCase):
    """[핀포인트 추가] 로그아웃 후에는 그 전에 발급됐던 refresh_token으로 갱신이 안 돼야 합니다."""

    async def test_logout_invalidates_refresh_token(self):
        signup_data = {
            "email": "logout@example.com",
            "password": "Password123!",
            "name": "로그아웃테스터",
            "gender": "FEMALE",
            "birth_date": "1992-02-02",
            "phone_number": "01077778888",
            "agreed_terms": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/v1/auth/signup", json=signup_data)
            login_response = await client.post(
                "/api/v1/auth/login", json={"email": "logout@example.com", "password": "Password123!"}
            )
            access_token = login_response.json()["access_token"]
            refresh_token = _extract_refresh_token(login_response)

            logout_response = await client.post(
                "/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
            )
            assert logout_response.status_code == status.HTTP_200_OK

            # 로그아웃 이후, 로그아웃 전에 받았던 refresh_token으로는 더 이상 갱신이 안 되어야 함
            client.cookies["refresh_token"] = refresh_token
            refresh_after_logout = await client.get("/api/v1/auth/token/refresh")
            assert refresh_after_logout.status_code == status.HTTP_401_UNAUTHORIZED
