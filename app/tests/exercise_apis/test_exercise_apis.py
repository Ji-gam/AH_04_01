from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

SIGNUP_BASE = {"password": "Password123!", "name": "운동테스터"}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_catalog_returns_full_fixed_exercise_list():
    """드롭다운용 - 검색어 없이 고정 시드 전체(23개)를 그대로 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "exercise_catalog@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/exercise/catalog", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    names = [item["exercise_name"] for item in response.json()["results"]]
    assert "달리기" in names
    assert "걷기" in names
    assert "줄넘기" in names
    assert len(names) == len(set(names))  # 중복 없음


async def test_catalog_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/exercise/catalog")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_estimate_met_returns_a_value_even_without_ai_worker_running():
    """ai_worker가 없는(또는 실패하는) 테스트 환경에서도 폴백 MET로 항상 200을 반환해야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "exercise_estimate@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/exercise/estimate-met", json={"exercise_name": "클라이밍"}, headers=headers
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["exercise_name"] == "클라이밍"
    assert body["met_value"] > 0


async def test_estimate_met_result_can_be_logged_as_duration_mode():
    """추정된 MET 값을 그대로 duration 모드로 기록할 수 있어야 한다(엔드투엔드 흐름)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "exercise_estimate_log@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        estimate_response = await client.post(
            "/api/v1/exercise/estimate-met", json={"exercise_name": "클라이밍"}, headers=headers
        )
        estimate = estimate_response.json()

        log_response = await client.post(
            "/api/v1/exercise/logs",
            json={
                "exercise_name": estimate["exercise_name"],
                "input_mode": "duration",
                "met_value": estimate["met_value"],
                "duration_minutes": 30,
            },
            headers=headers,
        )

    assert log_response.status_code == status.HTTP_201_CREATED
    logs = log_response.json()["logs"]
    assert any(log["exercise_name"] == "클라이밍" for log in logs)
