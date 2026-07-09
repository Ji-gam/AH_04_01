from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "건강정보테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01022223333",
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_get_health_info_default_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health1@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/users/me/health-info", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["height_cm"] is None
    assert body["weight_kg"] is None
    assert body["bmi"] is None
    assert body["diagnosis_history"] == []
    assert body["family_history"] == []


async def test_update_health_info_and_bmi_calculated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {
            "height_cm": 170,
            "weight_kg": 68,
            "diagnosis_history": ["DIABETES"],
            "family_history": ["CANCER", "HEART_DISEASE"],
            "special_notes": "페니실린 알레르기",
            "other_notes": "특이사항 없음",
        }
        response = await client.patch("/api/v1/users/me/health-info", json=update_data, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["height_cm"] == 170
    assert body["weight_kg"] == 68
    # 170cm/68kg -> bmi = 68 / (1.7 ** 2) = 23.5...
    assert body["bmi"] == 23.5
    assert body["diagnosis_history"] == ["DIABETES"]
    assert set(body["family_history"]) == {"CANCER", "HEART_DISEASE"}
    assert body["special_notes"] == "페니실린 알레르기"
    assert body["other_notes"] == "특이사항 없음"


async def test_update_health_info_invalid_height():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health3@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch("/api/v1/users/me/health-info", json={"height_cm": 999}, headers=headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_health_info_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/me/health-info")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
