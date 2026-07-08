"""
[T-PROFILE-1] 생체정보(키/체중/진단병력/가족력) 입력 API 테스트.
RAG 담당 조원 요청으로 추가된 필드 - 회원가입 직후 별도 화면에서 이 API를 호출한다.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_login_and_get_token(client: AsyncClient, email: str) -> str:
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "생체정보테스터",
        "gender": "MALE",
        "birth_date": "1990-01-01",
        "phone_number": "01022223333",
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_new_user_has_empty_biometric_info_by_default():
    """가입 직후(생체정보 입력 전)엔 height_cm/weight_kg가 null, 병력은 빈 리스트여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_default@example.com")
        response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    body = response.json()
    assert body["height_cm"] is None
    assert body["weight_kg"] is None
    assert body["diagnosis_history"] == []
    assert body["family_history"] == []


async def test_update_biometric_info_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_update@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch(
            "/api/v1/users/me/biometric-info",
            json={
                "height_cm": 175.5,
                "weight_kg": 68.2,
                "diagnosis_history": ["DIABETES"],
                "family_history": ["CANCER", "HEART_DISEASE"],
            },
            headers=headers,
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["height_cm"] == 175.5
    assert body["weight_kg"] == 68.2
    assert body["diagnosis_history"] == ["DIABETES"]
    assert sorted(body["family_history"]) == sorted(["CANCER", "HEART_DISEASE"])


async def test_update_biometric_info_partial_update_keeps_other_fields():
    """일부 필드만 보내면, 안 보낸 필드는 이전 값 그대로 유지되어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_partial@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.patch(
            "/api/v1/users/me/biometric-info",
            json={"height_cm": 160.0, "weight_kg": 55.0},
            headers=headers,
        )

        # 이번엔 height_cm만 수정
        response = await client.patch("/api/v1/users/me/biometric-info", json={"height_cm": 162.0}, headers=headers)

    body = response.json()
    assert body["height_cm"] == 162.0
    assert body["weight_kg"] == 55.0  # 안 보낸 필드는 유지되어야 함


async def test_update_biometric_info_explicit_empty_list_clears_history():
    """diagnosis_history를 명시적으로 []로 보내면 '해당 없음'으로 저장되어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_clear@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.patch(
            "/api/v1/users/me/biometric-info",
            json={"diagnosis_history": ["CANCER"]},
            headers=headers,
        )
        response = await client.patch(
            "/api/v1/users/me/biometric-info", json={"diagnosis_history": []}, headers=headers
        )

    assert response.json()["diagnosis_history"] == []


async def test_update_biometric_info_rejects_invalid_disease_value():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch(
            "/api/v1/users/me/biometric-info",
            json={"diagnosis_history": ["감기"]},  # 5대질환 목록에 없는 값
            headers=headers,
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_update_biometric_info_rejects_out_of_range_values():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_login_and_get_token(client, "biometric_range@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch("/api/v1/users/me/biometric-info", json={"height_cm": 999}, headers=headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_update_biometric_info_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/api/v1/users/me/biometric-info", json={"height_cm": 170})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
