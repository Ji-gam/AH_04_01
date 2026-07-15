from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.services.habit_service import HabitDef, pick_recommendations

SIGNUP_BASE = {"password": "Password123!", "name": "습관테스터"}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_get_recommendations_returns_base_set_for_profile_without_diagnosis():
    """질환을 등록하지 않은 프로필의 추천 목록은 기본 습관(물 마시기 5잔, 산책 1회) 2개뿐이고,
    아직 아무것도 선택 안 했으면 selected_keys는 비어있어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_reco_base@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/habits/recommendations", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    keys = [h["key"] for h in body["habits"]]
    assert keys == ["water", "walk"]
    assert body["selected_keys"] == []


async def test_get_recommendations_adds_disease_specific_habit():
    """당뇨를 등록한 프로필의 추천 목록엔 기본 2개 + 당뇨 맞춤 습관 1개, 총 3개가 내려와야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_reco_diabetes@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )

        response = await client.get("/api/v1/habits/recommendations", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    keys = [h["key"] for h in response.json()["habits"]]
    assert keys == ["water", "walk", "diabetes_walk"]


async def test_get_recommendations_drops_selected_key_no_longer_in_pool():
    """당뇨 습관(diabetes_walk)을 선택해둔 뒤 진단을 다른 질환으로 바꾸면(풀이 바뀌면),
    더 이상 오늘 고를 수 없는 옛 선택 키는 selected_keys에서 빠져야 한다 - 안 그러면 프론트가
    그 유령 키를 그대로 저장 요청에 다시 실어 보내 400을 받는다(회귀 재현: 진단명별 습관이
    LLM 생성으로 바뀌면서 실제로 발생한 버그)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_stale_selection@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["diabetes_walk"]}, headers=headers)

        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "LIVER_DISEASE", "detail": None}]},
            headers=headers,
        )
        response = await client.get("/api/v1/habits/recommendations", headers=headers)

    body = response.json()
    assert "diabetes_walk" not in [h["key"] for h in body["habits"]]
    assert "diabetes_walk" not in body["selected_keys"]


async def test_get_today_habits_is_empty_before_any_selection():
    """추천만 받고 아직 선택(POST /habits/selections)을 안 했으면 오늘의 습관은 빈 배열이고,
    all_completed도 (공허 참이 아니라) false여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_no_selection@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/habits/today", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["habits"] == []
    assert body["all_completed"] is False


async def test_select_habits_then_today_returns_only_selected():
    """추천 2개 중 1개(walk)만 골라 선택하면, /habits/today엔 그 1개만 나와야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_select_partial@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        select_response = await client.post("/api/v1/habits/selections", json={"habit_keys": ["walk"]}, headers=headers)
        today_response = await client.get("/api/v1/habits/today", headers=headers)

    assert select_response.status_code == status.HTTP_200_OK
    keys = [h["key"] for h in today_response.json()["habits"]]
    assert keys == ["walk"]


async def test_select_habits_rejects_key_not_in_recommendations():
    """오늘의 추천 목록에 없는 habit_key로 선택을 시도하면 400이어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_select_invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/habits/selections", json={"habit_keys": ["diabetes_walk"]}, headers=headers
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_select_habits_rejects_more_than_five():
    """6개 이상을 한 번에 선택하려고 하면 422(요청 검증 실패)여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_select_toomany@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/habits/selections",
            json={"habit_keys": ["water", "walk", "a", "b", "c", "d"]},
            headers=headers,
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_select_habits_replaces_previous_selection():
    """다시 선택하면 이전 선택은 사라지고 새 선택으로 완전히 교체돼야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_select_replace@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/v1/habits/selections", json={"habit_keys": ["water", "walk"]}, headers=headers)
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["walk"]}, headers=headers)
        response = await client.get("/api/v1/habits/today", headers=headers)

    keys = [h["key"] for h in response.json()["habits"]]
    assert keys == ["walk"]


async def test_check_habit_increments_progress_and_caps_at_target():
    """선택한 습관을 체크할 때마다 진행량이 1씩 늘고, 목표치를 넘어서 더 체크해도
    target 이상으로 올라가지 않는다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_check@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["water"]}, headers=headers)

        for _ in range(6):  # target(5)보다 한 번 더 클릭
            response = await client.post("/api/v1/habits/today/water/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    water = next(h for h in response.json()["habits"] if h["key"] == "water")
    assert water["progress"] == 5
    assert water["completed"] is True


async def test_check_habit_with_unknown_key_returns_404():
    """오늘 선택하지 않은(또는 애초에 존재하지 않는) habit_key로 체크하면 404여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_unknown@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/habits/today/diabetes_walk/check", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_all_completed_becomes_true_once_every_selected_habit_hits_target():
    """선택한 습관을 각자 목표치까지 채우면 all_completed가 true가 되어야 한다(칭찬 화면 트리거)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_all_done@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["water", "walk"]}, headers=headers)

        for _ in range(5):
            await client.post("/api/v1/habits/today/water/check", headers=headers)
        response = await client.post("/api/v1/habits/today/walk/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["all_completed"] is True


def test_pick_recommendations_returns_all_when_pool_within_limit():
    """후보가 MAX_RECOMMENDATIONS(10) 이하면 그대로 전부 반환한다."""
    pool = [HabitDef(key=f"h{i}", label=f"습관{i}", icon="🙂", unit="회", target=1) for i in range(8)]
    result = pick_recommendations(pool, profile_id=1, today=date(2026, 7, 15))
    assert result == pool


def test_pick_recommendations_rotates_without_consecutive_day_repeats():
    """후보가 10개를 넘으면(2단계: LLM이 후보를 늘리는 경우) 날짜가 하루 지날 때마다 정확히 한 칸씩
    밀려서, 연속된 이틀이 완전히 똑같은 10개로 겹치는 일이 없어야 한다(해시 나머지 방식의
    알려진 결함 재발 방지 회귀 테스트)."""
    pool = [HabitDef(key=f"h{i}", label=f"습관{i}", icon="🙂", unit="회", target=1) for i in range(14)]
    day1 = pick_recommendations(pool, profile_id=42, today=date(2026, 7, 14))
    day2 = pick_recommendations(pool, profile_id=42, today=date(2026, 7, 15))

    assert len(day1) == 10
    assert day1 != day2
