from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

SIGNUP_BASE = {"password": "Password123!", "name": "목표테스터"}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


def _numeric_payload(**overrides: object) -> dict:
    payload = {
        "title": "체중 감량",
        "start_value": 80,
        "target_value": 75,
        "unit": "kg",
        "start_date": "2026-07-01",
        "end_date": "2026-07-20",
    }
    payload.update(overrides)
    return payload


async def test_create_goal_returns_201_with_guide_content():
    """생성 즉시 F-GOAL-2 가이드가 함께 내려와야 한다(ai_worker 미가동 시 폴백 템플릿으로라도)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_create@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["title"] == "체중 감량"
    assert body["guide_content"]
    assert body["guide_generated_at"] is not None
    assert body["is_achieved"] is False
    assert body["term"] == "단기"


async def test_create_goal_without_goal_type_defaults_to_numeric():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_default_type@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)

    assert response.json()["goal_type"] == "NUMERIC"


async def test_create_frequency_goal_returns_frequency_type_and_zero_start():
    """횟수형은 시작/현재 수치를 0으로 보내고 goal_type=FREQUENCY로 만든다(운동하기 등)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_frequency@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        payload = _numeric_payload(
            title="주 3회 운동하기",
            goal_type="FREQUENCY",
            start_value=0,
            current_value=0,
            target_value=3,
            unit="회",
        )

        response = await client.post("/api/v1/goals", json=payload, headers=headers)

    body = response.json()
    assert body["goal_type"] == "FREQUENCY"
    assert body["current_value"] == 0
    assert body["target_value"] == 3


async def test_create_goal_rejects_missing_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/goals", json={"title": "제목만 있음"}, headers=headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_list_goals_scoped_to_profile():
    """다른 계정이 만든 목표는 내 목록에 보이면 안 된다(profile_id 기준 스코핑)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_a = await _signup_and_login(client, "goal_owner_a@example.com")
        token_b = await _signup_and_login(client, "goal_owner_b@example.com")
        await client.post(
            "/api/v1/goals", json=_numeric_payload(title="A의 목표"), headers={"Authorization": f"Bearer {token_a}"}
        )

        response = await client.get("/api/v1/goals", headers={"Authorization": f"Bearer {token_b}"})

    assert response.json()["goals"] == []


async def test_list_goals_includes_created_goal():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_list@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/goals", json=_numeric_payload(title="목록 확인용"), headers=headers)

        response = await client.get("/api/v1/goals", headers=headers)

    titles = [g["title"] for g in response.json()["goals"]]
    assert "목록 확인용" in titles


async def test_update_goal_changes_title_and_keeps_guide_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_update@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = (await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)).json()

        response = await client.patch(
            f"/api/v1/goals/{created['id']}", json={"title": "새 목표명"}, headers=headers
        )

    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert body["title"] == "새 목표명"
    assert body["guide_content"]


async def test_update_goal_not_found_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_update_missing@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.patch("/api/v1/goals/999999", json={"title": "없는 목표"}, headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_goal_owned_by_other_profile_returns_404():
    """다른 계정 소유 목표는 존재해도 404여야 한다(소유권 없음을 존재 안 함과 동일하게 취급)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_a = await _signup_and_login(client, "goal_hijack_owner@example.com")
        token_b = await _signup_and_login(client, "goal_hijack_attacker@example.com")
        created = (
            await client.post(
                "/api/v1/goals", json=_numeric_payload(), headers={"Authorization": f"Bearer {token_a}"}
            )
        ).json()

        response = await client.patch(
            f"/api/v1/goals/{created['id']}",
            json={"title": "가로채기 시도"},
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_log_progress_updates_current_value_and_progress_rate():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_log@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = (await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)).json()

        response = await client.post(
            f"/api/v1/goals/{created['id']}/logs", json={"value": 77.5}, headers=headers
        )

    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert body["current_value"] == 77.5
    assert body["progress_rate"] == 0.5


async def test_log_progress_same_day_upserts_not_duplicates_recent_logs():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_log_upsert@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = (await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)).json()
        log_date = "2026-07-15"

        await client.post(
            f"/api/v1/goals/{created['id']}/logs",
            json={"value": 79, "log_date": log_date},
            headers=headers,
        )
        response = await client.post(
            f"/api/v1/goals/{created['id']}/logs",
            json={"value": 78, "log_date": log_date},
            headers=headers,
        )

    body = response.json()
    same_day_logs = [log for log in body["recent_logs"] if log["log_date"] == log_date]
    assert len(same_day_logs) == 1
    assert same_day_logs[0]["value"] == 78


async def test_log_progress_for_nonexistent_goal_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_log_missing@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/goals/999999/logs", json={"value": 1}, headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_goal_removes_it_from_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_delete@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        created = (await client.post("/api/v1/goals", json=_numeric_payload(), headers=headers)).json()

        delete_response = await client.delete(f"/api/v1/goals/{created['id']}", headers=headers)
        list_response = await client.get("/api/v1/goals", headers=headers)

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert created["id"] not in [g["id"] for g in list_response.json()["goals"]]


async def test_delete_goal_not_found_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "goal_delete_missing@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.delete("/api/v1/goals/999999", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_goal_endpoints_require_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/goals")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
