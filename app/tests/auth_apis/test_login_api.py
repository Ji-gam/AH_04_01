import re
from datetime import datetime
from email.utils import parsedate_to_datetime

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
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    login_data = {"email": "login_test@example.com", "password": "Password123!"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)

        # 로그인 시도
        response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()
    # [CONVENTIONS.md 3-4] 로그인 응답 바디에는 profile_id도 포함되어야 한다
    assert "profile_id" in response.json()
    assert isinstance(response.json()["profile_id"], int)
    # 쿠키 검증 대신 응답 헤더 확인
    assert any("refresh_token" in header for header in response.headers.get_list("set-cookie"))

    # [T-AUTH-4 버그수정] 쿠키 만료시각이 access_token(60분) 기준이 아니라
    # refresh_token(14일) 기준으로 정확히 잡혀 있어야 한다. 예전 버그였다면 쿠키가
    # 60분 뒤 브라우저에서 삭제되거나(access 기준), 반대로 55년짜리로 새는 문제가 있었다.
    set_cookie_header = next(h for h in response.headers.get_list("set-cookie") if "refresh_token" in h)
    expires_match = re.search(r"expires=([^;]+)", set_cookie_header, re.IGNORECASE)
    assert expires_match is not None, f"expires가 쿠키 헤더에 없음: {set_cookie_header}"
    expires_dt = parsedate_to_datetime(expires_match.group(1))

    now = datetime.now(tz=expires_dt.tzinfo)
    seconds_until_expiry = (expires_dt - now).total_seconds()

    one_hour = 60 * 60  # access_token 만료시간(버그였다면 이 근처로 나옴)
    fourteen_days = 14 * 24 * 60 * 60  # refresh_token 만료시간(정상)
    one_year = 365 * 24 * 60 * 60

    assert seconds_until_expiry > one_hour * 2, "쿠키가 access_token(60분) 기준으로 짧게 만료되고 있음"
    assert seconds_until_expiry < one_year, "쿠키가 55년짜리 버그 상태로 만료되고 있음"
    assert abs(seconds_until_expiry - fourteen_days) < 3600, "쿠키 만료시간이 14일 근처가 아님"

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
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/signup", json=signup_data)
        response = await client.post(
            "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword999!"}
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
