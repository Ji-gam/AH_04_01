from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

SIGNUP_BASE = {"password": "Password123!", "name": "식단피드백테스터"}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_kcal_reason_feedback_accepts_and_returns_value():
    """GET /diet/today를 한 번 호출해 오늘의 기준 칼로리 이유가 생성된 뒤라면, 그 이유에 대한
    평가를 남길 수 있어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "diet_feedback_up@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.get("/api/v1/diet/today", headers=headers)

        response = await client.post("/api/v1/diet/kcal-reason-feedback", json={"value": "UP"}, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["value"] == "UP"


async def test_kcal_reason_feedback_re_vote_overwrites_previous_value():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "diet_feedback_revote@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.get("/api/v1/diet/today", headers=headers)

        await client.post("/api/v1/diet/kcal-reason-feedback", json={"value": "UP"}, headers=headers)
        response = await client.post(
            "/api/v1/diet/kcal-reason-feedback",
            json={"value": "DOWN", "comment": "일반적인 이야기였어요"},
            headers=headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["value"] == "DOWN"


async def test_kcal_reason_feedback_before_any_reason_generated_returns_404():
    """GET /diet/today를 한 번도 안 불러서 오늘의 이유가 아직 없으면 404여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "diet_feedback_missing@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/diet/kcal-reason-feedback", json={"value": "UP"}, headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
