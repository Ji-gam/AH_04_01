"""
[T-AUTH-6] Rate Limiting 테스트.
signup/login에 같은 IP로 1분당 5회 넘게 요청하면 6번째부터 429로 막혀야 한다.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def test_login_is_rate_limited_after_5_attempts_per_minute():
    login_data = {"email": "rate_limit_test@example.com", "password": "WrongPassword!"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        statuses = []
        for _ in range(6):
            response = await client.post("/api/v1/auth/login", json=login_data)
            statuses.append(response.status_code)

    # 처음 5번은 (비밀번호가 틀렸으니) 400이어야 하고, 6번째는 Rate Limit에 걸려 429여야 한다.
    assert statuses[:5] == [status.HTTP_400_BAD_REQUEST] * 5
    assert statuses[5] == status.HTTP_429_TOO_MANY_REQUESTS


async def test_signup_is_rate_limited_after_5_attempts_per_minute():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        statuses = []
        for i in range(6):
            signup_data = {
                "email": f"rate_limit_signup_{i}@example.com",
                "password": "Password123!",
                "name": "레이트리밋테스터",
                "gender": "MALE",
                "birth_date": "1990-01-01",
                "phone_number": f"0101111{i:04d}",
                "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
            }
            response = await client.post("/api/v1/auth/signup", json=signup_data)
            statuses.append(response.status_code)

    assert statuses[:5] == [status.HTTP_201_CREATED] * 5
    assert statuses[5] == status.HTTP_429_TOO_MANY_REQUESTS
