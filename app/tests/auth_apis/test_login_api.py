from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.services.jwt import JwtService


async def test_login_success():
    # 먼저 사용자 등록
    signup_data = {
        "email": "login_test@example.com",
        "password": "Password123!",
        "name": "로그인테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": "01011112222",
    }
    login_data = {"email": "login_test@example.com", "password": "Password123!"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        # 로그인 시도
        response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    # 쿠키 검증 대신 응답 헤더 확인
    assert any("refresh_token" in header for header in response.headers.get_list("set-cookie"))

    # 액세스 토큰에는 user_id뿐 아니라 profile_id도 담겨 있어야 한다 (도메인 라우터가 profile_id로 스코핑하기 때문)
    access_token = response.json()["access_token"]
    verified = JwtService().verify_jwt(token=access_token, token_type="access")
    assert "user_id" in verified.payload
    assert "profile_id" in verified.payload


async def test_login_invalid_credentials():
    login_data = {"email": "nonexistent@example.com", "password": "WrongPassword123!"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json=login_data)

    # AuthService.authenticate 에서 실패 시 HTTP_400_BAD_REQUEST 발생
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_login_wrong_password():
    signup_data = {
        "email": "wrongpw@example.com",
        "password": "Password123!",
        "name": "비번틀림테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01044445555",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        response = await client.post(
            "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword999!"}
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
