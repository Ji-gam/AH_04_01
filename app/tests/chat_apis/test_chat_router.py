import json

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "챗봇테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
        "agreements": {"service_terms": True, "privacy": True, "sensitive_info": True},
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_create_session_then_send_message_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "chat1@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        assert session_response.status_code == status.HTTP_200_OK
        session_id = session_response.json()["session_id"]

        message_response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "두통약 뭐가 좋아요?"},
        )

    assert message_response.status_code == status.HTTP_200_OK
    lines = [line for line in message_response.text.split("\n") if line.strip()]
    assert json.loads(lines[-1])["type"] == "done"


async def test_send_message_emergency_keyword_returns_fallback():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "chat2@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]

        message_response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "가슴 통증 있어요"},
        )

    assert "119" in message_response.text


async def test_send_message_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat/sessions/1/messages", json={"message": "hi"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_send_message_to_other_profiles_session_is_forbidden():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_token = await _signup_and_login(client, "owner@example.com")
        session_response = await client.post(
            "/api/v1/chat/sessions", headers={"Authorization": f"Bearer {owner_token}"}
        )
        session_id = session_response.json()["session_id"]

        intruder_token = await _signup_and_login(client, "intruder@example.com")
        response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"message": "hi"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
