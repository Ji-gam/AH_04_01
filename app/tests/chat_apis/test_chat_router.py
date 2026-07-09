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


async def test_list_chat_sessions_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "list_sess@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/v1/chat/sessions", headers=headers)
        await client.post("/api/v1/chat/sessions", headers=headers)

        list_response = await client.get("/api/v1/chat/sessions", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        sessions = list_response.json()
        assert len(sessions) >= 2


async def test_list_chat_messages_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "list_msg@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]

        await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "두통약 뭐가 좋아요?"},
        )

        msg_list_response = await client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
        assert msg_list_response.status_code == status.HTTP_200_OK
        messages = msg_list_response.json()
        assert len(messages) >= 2
        assert messages[0]["role"].lower() == "user"
        assert "두통약" in messages[0]["content"]


async def test_pregnant_concerta_dur_warning_in_chat():
    from sqlalchemy import select

    from app.models.profiles import Profile
    from app.tests.conftest import TestSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "preg_dur@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # DB에서 해당 프로필의 이름을 "임산부"로 업데이트
        async with TestSessionLocal() as session:
            result = await session.execute(select(Profile).order_by(Profile.id.desc()))
            profile = result.scalars().first()
            assert profile is not None
            profile.name = "임산부"
            await session.commit()

        # 세션 생성
        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]

        # 질문 전송
        message_response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "임신 중에 콘서타정 먹어도 괜찮나요?"},
        )

    assert message_response.status_code == status.HTTP_200_OK
    assert "식약처 DUR 안전 정보" in message_response.text


async def test_geriatric_diazepam_dur_warning_in_chat():
    from datetime import date

    from sqlalchemy import select

    from app.models.profiles import Profile
    from app.tests.conftest import TestSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "elder_dur@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # DB에서 해당 프로필을 만 65세 이상 노인 상태로 업데이트 (1950년생)
        async with TestSessionLocal() as session:
            result = await session.execute(select(Profile).order_by(Profile.id.desc()))
            profile = result.scalars().first()
            assert profile is not None
            profile.birthday = date(1950, 1, 1)
            await session.commit()

        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]

        message_response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "노인이 디아제팜을 먹어도 되나요?"},
        )

    assert message_response.status_code == status.HTTP_200_OK
    assert "식약처 DUR 안전 정보" in message_response.text
