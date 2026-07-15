from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.repositories.content_repository import ContentRepository
from app.services import content_generation_service as content_generation_service_module
from app.services.ai_worker_gateway import (
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
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


async def _seed_one_content(disease_code: str = "당뇨", category: str = "LIFESTYLE") -> int:
    async with TestSessionLocal() as session:
        content = await ContentRepository().save(
            session,
            disease_code=disease_code,
            category=category,
            content_date=_today_kst(),
            title="테스트 카드",
            summary="요약",
            body="본문",
            image_prompt=None,
        )
        return content.id


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


async def _fake_generate_content_card(disease_code: str, category: str, topic: str) -> dict:
    return {"title": f"{disease_code}-{category}-{topic}", "summary": "요약", "body": "본문", "image_prompt": None}


def _failing_generator(exc: Exception):
    async def _raise(disease_code: str, category: str, topic: str) -> dict:
        raise exc

    return _raise


async def test_generate_content_creates_card_with_specified_combo(monkeypatch):
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", _fake_generate_content_card)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/contents/generate", json={"disease_code": "당뇨", "category": "LIFESTYLE", "topic": "운동"}
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["disease_code"] == "당뇨"
    assert body["category"] == "LIFESTYLE"
    assert body["title"] == "당뇨-LIFESTYLE-운동"
    assert "id" in body


async def test_generate_content_picks_random_combo_when_body_omitted(monkeypatch):
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", _fake_generate_content_card)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/contents/generate", json={})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["disease_code"]


async def test_generate_content_second_click_updates_same_card_not_a_new_row(monkeypatch):
    """버튼을 반복 클릭해도(같은 질환/카테고리/오늘) 유니크 제약 위반 없이 같은 카드가 갱신된다."""
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", _fake_generate_content_card)
    payload = {"disease_code": "간질환", "category": "FOOD", "topic": "1차"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/contents/generate", json=payload)
        second = await client.post("/api/v1/contents/generate", json={**payload, "topic": "2차"})

    assert first.status_code == second.status_code == status.HTTP_200_OK
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["title"] == "간질환-FOOD-2차"


async def test_generate_content_returns_503_with_friendly_message_when_ai_worker_unavailable(monkeypatch):
    """ai_worker가 응답하지 않거나 생성 불가 상태(예: API 키 미설정)면, 기술적 에러 대신
    사용자 친화적 문구로 응답한다."""
    monkeypatch.setattr(
        content_generation_service_module,
        "generate_content_card",
        _failing_generator(AIWorkerUnavailableError("ai_worker 생성 불가")),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/contents/generate", json={})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "상담사가 잠시 자리를 비웠습니다" in response.json()["detail"]


async def test_generate_content_returns_400_on_invalid_request_to_ai_worker(monkeypatch):
    monkeypatch.setattr(
        content_generation_service_module,
        "generate_content_card",
        _failing_generator(AIWorkerInvalidRequestError("잘못된 요청")),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/contents/generate", json={})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_generate_content_returns_502_on_malformed_ai_worker_response(monkeypatch):
    monkeypatch.setattr(
        content_generation_service_module,
        "generate_content_card",
        _failing_generator(AIWorkerProcessingError("형식 이상")),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/contents/generate", json={})

    assert response.status_code == status.HTTP_502_BAD_GATEWAY


async def test_get_content_by_id_returns_200_with_full_item():
    content_id = await _seed_one_content(disease_code="당뇨", category="LIFESTYLE")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/contents/{content_id}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["id"] == content_id
    assert body["disease_code"] == "당뇨"
    assert body["title"] == "테스트 카드"


async def test_get_content_by_id_returns_404_when_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_related_contents_returns_same_disease_different_category_excluding_self():
    """상세화면의 "관련컨텐츠" - 같은 질환, 다른 카테고리만, 자기 자신은 제외."""
    base_id = await _seed_one_content(disease_code="당뇨", category="LIFESTYLE")
    await _seed_one_content(disease_code="당뇨", category="FOOD")
    await _seed_one_content(disease_code="암", category="FOOD")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/contents/{base_id}/related")

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["disease_code"] == "당뇨"
    assert items[0]["category"] == "FOOD"


async def test_get_related_contents_respects_limit_query_param():
    base_id = await _seed_one_content(disease_code="당뇨", category="LIFESTYLE")
    for category in ("FOOD", "MEDICAL_NEWS"):
        await _seed_one_content(disease_code="당뇨", category=category)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/contents/{base_id}/related", params={"limit": 1})

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()["items"]) == 1


async def test_get_related_contents_returns_404_when_base_content_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/contents/999999/related")

    assert response.status_code == status.HTTP_404_NOT_FOUND
