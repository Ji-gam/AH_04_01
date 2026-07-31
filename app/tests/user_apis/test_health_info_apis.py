from datetime import date

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
    assert body["birth_date"] is None
    assert body["gender"] is None
    assert body["height_cm"] is None
    assert body["weight_kg"] is None
    assert body["bmi"] is None
    assert body["diagnosis_history"] == []
    assert body["family_history"] == []


async def test_update_health_info_sets_birth_date_gender_and_calculates_bmi():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        update_data = {
            "birth_date": "1990-07-10",
            "gender": "FEMALE",
            "height_cm": 170,
            "weight_kg": 68,
            "diagnosis_history": [
                {
                    "disease": "DIABETES",
                    "disease_subtype": "제2형 당뇨",
                    "diagnosed_years_ago": 10,
                    "status": "UNCONTROLLED",
                    "on_medication": True,
                    "detail": "인슐린 투여 중",
                }
            ],
            "family_history": [
                {"disease": "CANCER", "disease_subtype": "폐암", "relation": "PARENT", "detail": None},
                {"disease": "OTHER", "disease_subtype": None, "relation": "GRANDPARENT", "detail": "외조모 파킨슨병"},
            ],
            "special_notes": "페니실린 알레르기",
            "other_notes": "특이사항 없음",
        }
        response = await client.patch("/api/v1/users/me/health-info", json=update_data, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["birth_date"] == "1990-07-10"
    # 오늘(테스트 실행일)이 생일(7/10) 이후면 age가 정확히 계산되어 나온다 - 값 자체보다
    # birth_date가 정확히 저장/반환되는지가 이 테스트의 핵심이라 age는 null이 아님만 확인한다.
    assert body["age"] is not None
    assert body["gender"] == "FEMALE"
    assert body["height_cm"] == 170
    assert body["weight_kg"] == 68
    # 170cm/68kg -> bmi = 68 / (1.7 ** 2) = 23.5...
    assert body["bmi"] == 23.5

    diagnosis = body["diagnosis_history"][0]
    assert diagnosis["disease"] == "DIABETES"
    assert diagnosis["disease_subtype"] == "제2형 당뇨"
    assert diagnosis["diagnosed_years_ago"] == 10
    assert diagnosis["status"] == "UNCONTROLLED"
    assert diagnosis["on_medication"] is True
    assert diagnosis["detail"] == "인슐린 투여 중"

    family_diseases = {entry["disease"] for entry in body["family_history"]}
    assert family_diseases == {"CANCER", "OTHER"}
    cancer_entry = next(e for e in body["family_history"] if e["disease"] == "CANCER")
    assert cancer_entry["disease_subtype"] == "폐암"
    assert cancer_entry["relation"] == "PARENT"
    other_entry = next(e for e in body["family_history"] if e["disease"] == "OTHER")
    assert other_entry["relation"] == "GRANDPARENT"
    assert other_entry["detail"] == "외조모 파킨슨병"
    assert body["special_notes"] == "페니실린 알레르기"
    assert body["other_notes"] == "특이사항 없음"


async def test_update_health_info_invalid_height():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health3@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.patch("/api/v1/users/me/health-info", json={"height_cm": 999}, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_update_health_info_very_old_birth_date_has_no_range_restriction():
    # 나이 제한 없음 - 건강관리는 나이와 무관하게 열려있어야 한다. 100세 이상도 문제없이 저장된다.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health4@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.patch(
            "/api/v1/users/me/health-info", json={"birth_date": "1900-01-01"}, headers=headers
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["birth_date"] == "1900-01-01"


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


async def test_update_health_info_without_birth_date_keeps_age_null():
    # 생년월일을 안 주면 나이도 계산할 수 없어 null이다.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health6@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.patch("/api/v1/users/me/health-info", json={"gender": "MALE"}, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["age"] is None
    assert body["birth_date"] is None


async def test_update_health_info_computes_age_from_birth_date():
    """생년월일로 만 나이가 계산되는지 확인한다. 정확한 경계값(생일 전/후, 윤년) 계산 로직 자체는
    이미 test_age_calculator.py에서 커버하므로, 여기서는 API 응답에 실제로 반영되는지만 본다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health7@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        today = date.today()
        birth_date = today.replace(year=today.year - 30)  # 오늘이 생일이라고 가정 -> 정확히 30살

        response = await client.patch(
            "/api/v1/users/me/health-info",
            json={"birth_date": birth_date.isoformat()},
            headers=headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["age"] == 30


async def test_update_health_info_sets_is_pregnant():
    """[#71 해결] 임신 여부를 선택 입력받아 저장/조회할 수 있어야 한다 - 채팅 임부금기 DUR
    경고 실연동의 데이터 소스가 된다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health8@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch(
            "/api/v1/users/me/health-info", json={"gender": "FEMALE", "is_pregnant": True}, headers=headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_pregnant"] is True


async def test_health_info_is_pregnant_defaults_to_null_when_unanswered():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "health9@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/users/me/health-info", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_pregnant"] is None
