from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette import status

from app.main import app
from app.models.chat import ChatMessageFeedback, MessageRole
from app.repositories.chat_repository import ChatRepository
from app.tests.conftest import TestSessionLocal


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    phone_number = "010" + str(abs(hash(email)))[:8]
    signup_data = {
        "email": email,
        "password": "Password123!",
        "name": "피드백테스터",
        "gender": "FEMALE",
        "birth_date": "1995-05-05",
        "phone_number": phone_number,
    }
    await client.post("/api/v1/auth/signup", json=signup_data)
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def _create_session_with_message_pair(email: str) -> tuple[str, int]:
    """전체 챗봇 스트리밍(ai_worker 네트워크 호출)을 거치지 않고, 피드백 API가 실제로
    필요로 하는 최소 데이터(세션 1개 + user/assistant 메시지 1쌍)만 직접 만든다 - trace_id는
    Langfuse 미설정 환경(로컬/CI)과 동일하게 항상 None으로 저장한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, email)
        session_response = await client.post("/api/v1/chat/sessions", headers={"Authorization": f"Bearer {token}"})
    session_id = int(session_response.json()["session_id"])

    repo = ChatRepository()
    async with TestSessionLocal() as session:
        await repo.save_message(session, session_id, MessageRole.USER, "두통약 뭐가 좋아요?")
        assistant_message = await repo.save_message(
            session, session_id, MessageRole.ASSISTANT, "타이레놀을 추천합니다."
        )

    return token, assistant_message.id


async def test_feedback_on_other_profiles_message_returns_404():
    _, message_id = await _create_session_with_message_pair("feedback_owner@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        intruder_token = await _signup_and_login(client, "feedback_intruder@example.com")
        response = await client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"value": "up"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_feedback_on_nonexistent_message_returns_404():
    token, _ = await _create_session_with_message_pair("feedback_missing@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/messages/999999999/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "up"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_feedback_on_user_message_is_rejected():
    """사용자 자신의 질문에는 별점을 매길 수 없다 - 어시스턴트 메시지 전용."""
    token, assistant_message_id = await _create_session_with_message_pair("feedback_user_msg@example.com")
    user_message_id = assistant_message_id - 1  # save_message가 USER 다음 ASSISTANT 순으로 저장한다

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/chat/messages/{user_message_id}/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "up"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_feedback_upsert_updates_existing_row_instead_of_creating_new_one():
    token, message_id = await _create_session_with_message_pair("feedback_upsert@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(f"/api/v1/chat/messages/{message_id}/feedback", headers=headers, json={"value": "up"})
        second = await client.post(
            f"/api/v1/chat/messages/{message_id}/feedback",
            headers=headers,
            json={"value": "down", "comment": "부정확함"},
        )

    # Langfuse 미설정(trace_id=None) 환경에서도 DB 저장만으로 항상 204를 반환해야 한다.
    assert first.status_code == status.HTTP_204_NO_CONTENT
    assert second.status_code == status.HTTP_204_NO_CONTENT

    async with TestSessionLocal() as session:
        result = await session.execute(select(ChatMessageFeedback).where(ChatMessageFeedback.message_id == message_id))
        rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].value == "DOWN"
    assert rows[0].comment == "부정확함"
