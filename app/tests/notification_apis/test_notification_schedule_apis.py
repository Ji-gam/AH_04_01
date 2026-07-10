from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

SIGNUP_BASE = {
    "password": "Password123!",
    "name": "알림테스터",
    "gender": "FEMALE",
    "birth_date": "1993-03-03",
}


async def _signup_and_login(client: AsyncClient, email: str, phone_number: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email, "phone_number": phone_number})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_create_notification_schedule_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_create@example.com", "01011110001")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "타이레놀", "frequency_type": "DAILY", "alarm_time": "08:30:00"},
            headers=headers,
        )
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["medication_name"] == "타이레놀"
    assert body["frequency_type"] == "DAILY"
    assert body["target_day_of_week"] is None
    assert body["is_active"] is True


async def test_create_notification_schedule_weekly_without_day_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_create_fail@example.com", "01011110002")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "타이레놀", "frequency_type": "WEEKLY", "alarm_time": "08:30:00"},
            headers=headers,
        )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_list_notification_schedules_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_list@example.com", "01011110003")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "비타민", "frequency_type": "DAILY", "alarm_time": "09:00:00"},
            headers=headers,
        )
        response = await client.get("/api/v1/notifications/schedules", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["medication_name"] == "비타민"


async def test_list_notification_schedules_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/notifications/schedules")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_update_notification_schedule_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_update@example.com", "01011110004")
        headers = {"Authorization": f"Bearer {token}"}
        create_response = await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "타이레놀", "frequency_type": "DAILY", "alarm_time": "08:30:00"},
            headers=headers,
        )
        schedule_id = create_response.json()["id"]
        response = await client.patch(
            f"/api/v1/notifications/schedules/{schedule_id}",
            json={"medication_name": "게보린", "alarm_time": "09:15:00"},
            headers=headers,
        )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["medication_name"] == "게보린"
    assert body["alarm_time"] == "09:15:00"


async def test_update_notification_schedule_not_owned_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_token = await _signup_and_login(client, "ntfy_owner@example.com", "01011110005")
        other_token = await _signup_and_login(client, "ntfy_other@example.com", "01011110006")
        create_response = await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "타이레놀", "frequency_type": "DAILY", "alarm_time": "08:30:00"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        schedule_id = create_response.json()["id"]
        response = await client.patch(
            f"/api/v1/notifications/schedules/{schedule_id}",
            json={"medication_name": "게보린"},
            headers={"Authorization": f"Bearer {other_token}"},
        )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_notification_schedule_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_delete@example.com", "01011110007")
        headers = {"Authorization": f"Bearer {token}"}
        create_response = await client.post(
            "/api/v1/notifications/schedules",
            json={"medication_name": "타이레놀", "frequency_type": "DAILY", "alarm_time": "08:30:00"},
            headers=headers,
        )
        schedule_id = create_response.json()["id"]
        delete_response = await client.delete(f"/api/v1/notifications/schedules/{schedule_id}", headers=headers)
        list_response = await client.get("/api/v1/notifications/schedules", headers=headers)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert list_response.json() == []


async def test_delete_notification_schedule_not_found_fails():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "ntfy_delete_fail@example.com", "01011110008")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.delete("/api/v1/notifications/schedules/999999", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
