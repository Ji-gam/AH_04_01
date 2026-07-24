from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    signup_data = {"email": email, "password": "password123!", "name": "질환검색테스터"}
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123!"})
    return login_response.json()["access_token"]


async def test_search_disease_subtypes_finds_seeded_data():
    # 마이그레이션에서 미리 심어둔 데이터("폐암" 등)가 검색되는지 확인.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "subtype1@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/diseases/CANCER/subtypes", params={"q": "폐"}, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    names = [item["name"] for item in response.json()]
    assert "폐암" in names
    # 전부 미리 심어둔 데이터라 is_custom=False 여야 함
    assert all(item["is_custom"] is False for item in response.json() if item["name"] == "폐암")


async def test_search_disease_subtypes_empty_query_lists_all_in_category():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "subtype2@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/diseases/DIABETES/subtypes", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    names = {item["name"] for item in response.json()}
    assert "제2형 당뇨병" in names
    assert "제1형 당뇨병" in names


async def test_search_disease_subtypes_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/diseases/CANCER/subtypes")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_new_subtype_is_auto_created_and_then_searchable():
    # 목록에 없는 이름으로 개인건강정보를 저장하면 -> 매핑테이블에 is_custom=True로 새로 생기고,
    # 그 다음부터는(같은 사람이든 다른 사람이든) 검색에 잡혀야 한다 - 원티드 스킬태그와 동일한 동작.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "subtype3@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # 처음엔 검색해도 없어야 함
        before = await client.get("/api/v1/diseases/CANCER/subtypes", params={"q": "희귀암테스트"}, headers=headers)
        assert before.json() == []

        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "CANCER", "disease_subtype": "희귀암테스트"}]},
            headers=headers,
        )

        after = await client.get("/api/v1/diseases/CANCER/subtypes", params={"q": "희귀암테스트"}, headers=headers)

    assert after.status_code == status.HTTP_200_OK
    matched = [item for item in after.json() if item["name"] == "희귀암테스트"]
    assert len(matched) == 1
    assert matched[0]["is_custom"] is True


async def test_same_subtype_name_is_not_duplicated():
    # 두 명이 같은 질환명을 입력해도 disease_subtypes에는 한 행만 생겨야 한다(get_or_create).
    from sqlalchemy import select

    from app.models.disease_entries import DiseaseSubtype
    from app.tests.conftest import TestSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token1 = await _signup_and_login(client, "subtype4a@example.com")
        token2 = await _signup_and_login(client, "subtype4b@example.com")

        for token in (token1, token2):
            await client.patch(
                "/api/v1/users/me/health-info",
                json={"diagnosis_history": [{"disease": "LIVER_DISEASE", "disease_subtype": "중복테스트간질환"}]},
                headers={"Authorization": f"Bearer {token}"},
            )

    async with TestSessionLocal() as session:
        result = await session.execute(select(DiseaseSubtype).where(DiseaseSubtype.name == "중복테스트간질환"))
        rows = result.scalars().all()

    assert len(rows) == 1
