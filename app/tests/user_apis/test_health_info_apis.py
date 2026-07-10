from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    # [가입 최소화] 나이/성별은 여기서 안 받는다 - 개인건강정보에서 처음 입력받는다.
    signup_data = {"email": email, "password": "password123!", "name": "건강정보테스터"}
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123!"})
    return login_response.json()["access_token"]


async def test_get_health_info_default_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health1@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/users/me/health-info", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["age"] is None
    assert body["gender"] is None
    assert body["height_cm"] is None
    assert body["weight_kg"] is None
    assert body["bmi"] is None
    assert body["diagnosis_history"] == []
    assert body["family_history"] == []


async def test_update_health_info_sets_age_gender_and_calculates_bmi():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {
            "age": 35,
            "gender": "FEMALE",
            "height_cm": 170,
            "weight_kg": 68,
            "diagnosis_history": [{"disease": "DIABETES", "detail": "10년째 인슐린 투여 중"}],
            "family_history": [
                {"disease": "CANCER", "detail": None},
                {"disease": "OTHER", "detail": "외조모 파킨슨병"},
            ],
            "special_notes": "페니실린 알레르기",
            "other_notes": "특이사항 없음",
        }
        response = await client.patch("/api/v1/users/me/health-info", json=update_data, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["age"] == 35
    assert body["gender"] == "FEMALE"
    assert body["height_cm"] == 170
    assert body["weight_kg"] == 68
    # 170cm/68kg -> bmi = 68 / (1.7 ** 2) = 23.5...
    assert body["bmi"] == 23.5
    assert body["diagnosis_history"] == [{"disease": "DIABETES", "detail": "10년째 인슐린 투여 중"}]
    family_diseases = {entry["disease"] for entry in body["family_history"]}
    assert family_diseases == {"CANCER", "OTHER"}
    other_entry = next(e for e in body["family_history"] if e["disease"] == "OTHER")
    assert other_entry["detail"] == "외조모 파킨슨병"
    assert body["special_notes"] == "페니실린 알레르기"
    assert body["other_notes"] == "특이사항 없음"


async def test_update_health_info_invalid_height():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health3@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.patch("/api/v1/users/me/health-info", json={"height_cm": 999}, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_update_health_info_age_has_no_range_restriction():
    # 나이 제한 없음 - 건강관리는 나이와 무관하게 열려있어야 한다.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health4@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.patch("/api/v1/users/me/health-info", json={"age": 200}, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["age"] == 200


async def test_update_health_info_empty_list_clears_disease_history():
    # 빈 리스트([])를 보내면 "질병 없음" 상태로 확정된다.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health5@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )
        response = await client.patch("/api/v1/users/me/health-info", json={"diagnosis_history": []}, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["diagnosis_history"] == []


async def test_health_info_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/users/me/health-info")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
