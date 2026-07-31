import re

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def test_token_refresh_success():
    # 사용자 등록 및 로그인하여 리프레시 토큰 획득
    signup_data = {
        "email": "refresh@example.com",
        "password": "Password123!",
        "name": "리프레시테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01099998888",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        login_response = await client.post(
            "/api/v1/auth/login", json={"email": "refresh@example.com", "password": "Password123!"}
        )

        # 쿠키에서 refresh_token 추출
        set_cookie = login_response.headers.get("set-cookie")
        refresh_token = ""
        if set_cookie:
            match = re.search(r"refresh_token=([^;]+)", set_cookie)
            if match:
                refresh_token = match.group(1)

        # 토큰 갱신 시도
        client.cookies["refresh_token"] = refresh_token
        response = await client.get("/api/v1/auth/token/refresh")
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


async def test_token_refresh_missing_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/token/refresh")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Refresh token is missing."


async def test_token_refresh_invalid_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies["refresh_token"] = "not-a-real-token"
        response = await client.get("/api/v1/auth/token/refresh")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_token_refresh_rotates_and_old_token_cannot_be_reused():
    """리프레시 토큰을 한 번 쓰면 그 값은 즉시 무효화되고, 응답에 새 refresh_token 쿠키가 내려와야 한다.
    예전(이미 쓴) 토큰으로 다시 시도하면 실패해야 한다(재사용 탐지)."""
    signup_data = {
        "email": "rotate_test@example.com",
        "password": "Password123!",
        "name": "로테이션테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": "rotate_test@example.com", "password": "Password123!"}
        )
        old_refresh_token = re.search(r"refresh_token=([^;]+)", login_response.headers.get("set-cookie")).group(1)

        client.cookies["refresh_token"] = old_refresh_token
        first_refresh = await client.get("/api/v1/auth/token/refresh")
        assert first_refresh.status_code == status.HTTP_200_OK

        # 응답에 새 refresh_token 쿠키가 내려와서, 이전 값과 달라야 한다(로테이션 확인).
        new_set_cookie = first_refresh.headers.get("set-cookie")
        new_refresh_token = re.search(r"refresh_token=([^;]+)", new_set_cookie).group(1)
        assert new_refresh_token != old_refresh_token

        # 예전(이미 쓴) 토큰으로 다시 시도 -> 재사용 탐지로 실패해야 한다.
        client.cookies["refresh_token"] = old_refresh_token
        reuse_attempt = await client.get("/api/v1/auth/token/refresh")

    assert reuse_attempt.status_code == status.HTTP_401_UNAUTHORIZED
    assert "재사용" in reuse_attempt.json()["detail"]


async def test_token_reuse_detection_revokes_all_sessions():
    """예전 토큰 재사용이 감지되면, 그 사이 새로 발급받은(아직 안 쓴) 토큰까지도 전부 무효화되어야 한다."""
    signup_data = {
        "email": "reuse_detect_test@example.com",
        "password": "Password123!",
        "name": "재사용탐지테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        login_response = await client.post(
            "/api/v1/auth/login", json={"email": "reuse_detect_test@example.com", "password": "Password123!"}
        )
        old_refresh_token = re.search(r"refresh_token=([^;]+)", login_response.headers.get("set-cookie")).group(1)

        client.cookies["refresh_token"] = old_refresh_token
        first_refresh = await client.get("/api/v1/auth/token/refresh")
        new_refresh_token = re.search(r"refresh_token=([^;]+)", first_refresh.headers.get("set-cookie")).group(1)

        # 예전 토큰 재사용 시도 (탈취 의심 상황 재현) -> 전체 세션 강제 로그아웃 트리거
        client.cookies["refresh_token"] = old_refresh_token
        await client.get("/api/v1/auth/token/refresh")

        # 재사용 탐지 이후엔, 방금 정상적으로 새로 받았던 토큰(new_refresh_token)까지도 무효화되어
        # 더 이상 쓸 수 없어야 한다(계정 전체 강제 로그아웃).
        client.cookies["refresh_token"] = new_refresh_token
        response_after_detection = await client.get("/api/v1/auth/token/refresh")

    assert response_after_detection.status_code == status.HTTP_401_UNAUTHORIZED
