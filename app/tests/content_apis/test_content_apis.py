from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.repositories.content_repository import ContentRepository
from app.services.content_service import _today_kst
from app.tests.conftest import TestSessionLocal


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "콘텐츠테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def _seed_one_content(disease_code: str = "당뇨", category: str = "LIFESTYLE") -> None:
    async with TestSessionLocal() as session:
        await ContentRepository().save(
            session,
            disease_code=disease_code,
            category=category,
            content_date=_today_kst(),
            title="테스트 카드",
            summary="요약",
            body="본문",
            image_prompt=None,
        )


async def test_get_contents_without_auth_returns_200_with_all_content_not_personalized():
    """'정보' 탭은 로그인 없이도 볼 수 있어야 한다."""
    await _seed_one_content()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/me")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["personalized"] is False
    assert len(body["items"]) == 1
    assert body["items"][0]["disease_code"] == "당뇨"


async def test_get_contents_for_profile_without_conditions_returns_all_content_not_personalized():
    """질환 미등록 프로필은 비로그인과 동일하게 전체 콘텐츠를 본다."""
    await _seed_one_content()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "content-nocond@example.com")
        response = await client.get("/api/v1/contents/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["personalized"] is False
    assert len(body["items"]) == 1


async def test_get_contents_with_category_filter_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/me", params={"category": "FOOD"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"personalized": False, "items": []}


async def test_get_contents_with_invalid_category_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/me", params={"category": "NOT_A_CATEGORY"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_get_contents_with_limit_returns_only_that_many_newest_items():
    await _seed_one_content(disease_code="당뇨", category="LIFESTYLE")
    await _seed_one_content(disease_code="암", category="FOOD")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/me", params={"limit": 1})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1


async def test_get_contents_for_profile_with_registered_disease_returns_personalized_content():
    """등록된 진단병력(diagnosis_history)이 있으면 그 질환 콘텐츠만 personalized=true로 받는다."""
    await _seed_one_content(disease_code="당뇨", category="LIFESTYLE")
    await _seed_one_content(disease_code="암", category="FOOD")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "content-diabetes@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )
        response = await client.get("/api/v1/contents/me", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["personalized"] is True
    assert {item["disease_code"] for item in body["items"]} == {"당뇨"}
