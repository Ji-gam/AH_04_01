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


async def test_login_locks_account_after_max_failed_attempts():
    """5회 연속 비밀번호 실패 시 계정이 잠기고, 그 다음부턴 올바른 비밀번호로도 로그인이 막혀야 한다."""
    signup_data = {
        "email": "lockout_test@example.com",
        "password": "Password123!",
        "name": "잠금테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        wrong_login = {"email": "lockout_test@example.com", "password": "WrongPassword999!"}
        last_response = None
        for _ in range(5):
            last_response = await client.post("/api/v1/auth/login", json=wrong_login)
            assert last_response.status_code == status.HTTP_400_BAD_REQUEST

        # 5번째 실패로 잠겼으니, 이제 올바른 비밀번호를 넣어도 잠금(423)에 걸려야 한다.
        correct_login = {"email": "lockout_test@example.com", "password": "Password123!"}
        locked_response = await client.post("/api/v1/auth/login", json=correct_login)

    assert locked_response.status_code == status.HTTP_423_LOCKED
    assert "잠겼습니다" in locked_response.json()["detail"]


async def test_login_success_resets_failed_attempt_counter():
    """실패를 몇 번 하다가 성공하면, 실패 카운터가 초기화되어 그 다음부턴 다시 5번을 채워야 잠긴다."""
    signup_data = {
        "email": "reset_counter_test@example.com",
        "password": "Password123!",
        "name": "초기화테스터",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        wrong_login = {"email": "reset_counter_test@example.com", "password": "WrongPassword999!"}
        for _ in range(3):
            await client.post("/api/v1/auth/login", json=wrong_login)

        # 3번 실패 후 성공 로그인 -> 카운터 초기화되어야 함
        correct_login = {"email": "reset_counter_test@example.com", "password": "Password123!"}
        success_response = await client.post("/api/v1/auth/login", json=correct_login)
        assert success_response.status_code == status.HTTP_200_OK

        # 초기화됐으니, 3번만 더 실패해서는(총 3+3=6번째지만 카운터는 리셋됐으므로) 아직 안 잠겨야 한다.
        for _ in range(3):
            still_unlocked = await client.post("/api/v1/auth/login", json=wrong_login)
            assert still_unlocked.status_code == status.HTTP_400_BAD_REQUEST  # 423 아니어야 함
