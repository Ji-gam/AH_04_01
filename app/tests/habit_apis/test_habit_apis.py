from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

SIGNUP_BASE = {"password": "Password123!", "name": "습관테스터"}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_get_today_habits_returns_base_set_for_profile_without_diagnosis():
    """질환을 등록하지 않은 프로필은 기본 습관(물 마시기 5잔, 산책 1회) 2개만 내려와야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_base@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/habits/today", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    keys = [h["key"] for h in body["habits"]]
    assert keys == ["water", "walk"]
    assert body["habits"][0]["target"] == 5
    assert body["habits"][0]["progress"] == 0
    assert body["habits"][0]["completed"] is False
    assert body["all_completed"] is False


async def test_get_today_habits_adds_disease_specific_habit():
    """당뇨를 등록한 프로필은 기본 2개 + 당뇨 맞춤 습관 1개, 총 3개가 내려와야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_diabetes@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )

        response = await client.get("/api/v1/habits/today", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    keys = [h["key"] for h in response.json()["habits"]]
    assert keys == ["water", "walk", "diabetes_walk"]


async def test_check_habit_increments_progress_and_caps_at_target():
    """체크할 때마다 진행량이 1씩 늘고, 목표치를 넘어서 더 체크해도 target 이상으로 올라가지 않는다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_check@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(6):  # target(5)보다 한 번 더 클릭
            response = await client.post("/api/v1/habits/today/water/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    water = next(h for h in response.json()["habits"] if h["key"] == "water")
    assert water["progress"] == 5
    assert water["completed"] is True


async def test_get_today_habits_picks_only_3_when_candidate_pool_exceeds_3():
    """질환을 2개 등록하면 후보(기본 2개+질환 2개=4개) 중 오늘 3개만 나오고,
    같은 날 다시 조회해도 같은 3개가 나와야 한다(자정 전까지는 안 바뀜)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_rotation@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={
                "diagnosis_history": [
                    {"disease": "DIABETES", "detail": None},
                    {"disease": "HEART_DISEASE", "detail": None},
                ]
            },
            headers=headers,
        )

        response1 = await client.get("/api/v1/habits/today", headers=headers)
        response2 = await client.get("/api/v1/habits/today", headers=headers)

    keys1 = [h["key"] for h in response1.json()["habits"]]
    keys2 = [h["key"] for h in response2.json()["habits"]]
    assert len(keys1) == 3
    assert keys1 == keys2


async def test_check_habit_with_unknown_key_returns_404():
    """지금 프로필이 갖고 있지 않은 습관 키(예: 등록 안 한 질환의 습관)로 체크하면 404여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_unknown@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/habits/today/diabetes_walk/check", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_all_completed_becomes_true_once_every_habit_hits_target():
    """모든 습관을 각자 목표치까지 채우면 all_completed가 true가 되어야 한다(칭찬 화면 트리거)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_all_done@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        for _ in range(5):
            await client.post("/api/v1/habits/today/water/check", headers=headers)
        response = await client.post("/api/v1/habits/today/walk/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["all_completed"] is True
