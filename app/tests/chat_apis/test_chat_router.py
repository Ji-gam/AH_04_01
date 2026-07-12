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
        # 프론트(useChatStream.ts)가 role을 소문자로 비교해 정렬 방향을 정하므로
        # (chat/ChatPage.tsx: m.role === "user"), API는 반드시 소문자로 내려야 한다.
        # DTO(app/dtos/chat.py)의 문서화된 예시도 "user"/"assistant"(소문자)다.
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert "두통약" in messages[0]["content"]


# [주의] "임산부" 이름 기반 DUR 경고 통합테스트는 삭제했다 — Profile 스키마에 임신 여부
# 필드가 없어(#71에서 추가 요청 중) is_pregnant가 항상 False로 고정되는 한 이 경로는
# 구조적으로 재현 불가능하다. 임부금기 게이팅 로직 자체의 커버리지는
# app/tests/services/test_chat_service.py::test_collect_dur_warnings_gates_on_pregnant_flag가 담당한다.


async def test_geriatric_diazepam_dur_warning_in_chat():
    from sqlalchemy import select

    from app.models.medication_model import Medication, MedicationSchedule
    from app.models.profiles import Profile
    from app.repositories.medication_repository import MedicationRepository
    from app.tests.conftest import TestSessionLocal

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "elder_dur@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # DB에서 해당 프로필을 만 65세 이상 노인 상태로 업데이트하고, 실제 복약 스케줄을 등록한다.
        async with TestSessionLocal() as session:
            result = await session.execute(select(Profile).order_by(Profile.id.desc()))
            profile = result.scalars().first()
            assert profile is not None
            profile.age = 76
            await session.commit()

            repo = MedicationRepository()
            medication = await repo.create_medication(
                session,
                Medication(medication_name="디아제팜", form_type="TABLET"),
            )
            await repo.create_schedule(
                session,
                MedicationSchedule(profile_id=profile.id, medication_id=medication.id, times=["08:00"]),
            )

        session_response = await client.post("/api/v1/chat/sessions", headers=headers)
        session_id = session_response.json()["session_id"]

        message_response = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "노인이 디아제팜을 먹어도 되나요?"},
        )

    assert message_response.status_code == status.HTTP_200_OK
    assert "식약처 DUR 안전 정보" in message_response.text
