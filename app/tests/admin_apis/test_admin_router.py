from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.services.ai_worker_gateway import AIWorkerGateway


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "관리자테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_admin_endpoint_unauthorized_without_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/chat/sessions")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_list_all_chat_sessions_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "admin_chat_list@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/v1/chat/sessions", headers=headers)

        response = await client.get("/api/v1/admin/chat/sessions", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    sessions = response.json()
    assert len(sessions) >= 1
    assert sessions[0]["profile_name"] == "관리자테스터"


async def test_get_admin_chat_session_messages_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "admin_chat_msg@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]
        await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages", headers=headers, json={"message": "두통약 뭐가 좋아요?"}
        )

        response = await client.get(f"/api/v1/admin/chat/sessions/{session_id}/messages", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    messages = response.json()
    assert len(messages) >= 2


async def test_get_admin_chat_session_messages_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "admin_chat_404@example.com")

        response = await client.get(
            "/api/v1/admin/chat/sessions/999999/messages", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_rag_ingest_status_proxies_to_gateway(monkeypatch):
    # sources는 source/(드롭 폴더)와 _manifest.yaml 대조 결과다. unregistered가 프론트까지
    # 그대로 전달되어야 "넣었는데 아무 반응 없음"이 사라진다.
    payload = {
        "dur_rules_count": 10,
        "pubmed_papers_count": 5,
        "papers_raw_counts": {"암": 3},
        "sources": {
            "indexed": ["dur_pwnm_taboo.csv"],
            "excluded": ["item_ingredient_map.csv"],
            "unregistered": ["방금던져넣은거.csv"],
            "missing": [],
        },
    }

    async def fake_ingest_status(self):
        return payload

    monkeypatch.setattr(AIWorkerGateway, "ingest_status", fake_ingest_status)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "admin_rag_status@example.com")

        response = await client.get("/api/v1/admin/rag/ingest/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == payload


async def test_rag_trigger_paper_ingest_proxies_to_gateway(monkeypatch):
    async def fake_trigger(self, categories, retmax_per_category):
        assert categories is None
        assert retmax_per_category is None
        return {"status": "started"}

    monkeypatch.setattr(AIWorkerGateway, "trigger_paper_ingest", fake_trigger)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "admin_rag_trigger@example.com")

        response = await client.post(
            "/api/v1/admin/rag/ingest/papers",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "started"}
