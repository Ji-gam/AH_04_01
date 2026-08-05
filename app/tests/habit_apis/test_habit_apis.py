from datetime import date

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.services import habit_service
from app.services.habit_service import BASE_HABITS, pick_recommendations

SIGNUP_BASE = {"password": "Password123!", "name": "습관테스터"}
BASE_HABIT_KEYS = {h.key for h in BASE_HABITS}


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/api/v1/auth/signup", json={**SIGNUP_BASE, "email": email})
    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login_response.json()["access_token"]


async def test_get_recommendations_returns_base_set_for_profile_without_diagnosis():
    """질환을 등록하지 않은 프로필도 매일 5개(MAX_RECOMMENDATIONS)를 기본 세트에서 채워서
    받아야 하고, 아직 아무것도 선택 안 했으면 selected_keys는 비어있어야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_reco_base@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/habits/recommendations", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    keys = [h["key"] for h in body["habits"]]
    assert len(keys) == 5
    assert set(keys) <= BASE_HABIT_KEYS
    assert body["selected_keys"] == []


async def test_get_recommendations_adds_disease_specific_habit(monkeypatch):
    """당뇨를 등록한(질병 1개) 프로필은 질병 맞춤 습관(diabetes_walk 등)이 후보군에 들어가야
    하고, BASE_HABITS도 함께 섞여야 한다 - "질병 1개면 등록된 습관 3개 + 기본 습관 2개"라는
    설계(2026-08-05). 오늘의 회전 로직(MAX_RECOMMENDATIONS)은 별도로 테스트하므로, 여기서는
    회전에 가려지지 않게 상한을 넉넉히 늘려 전체 질병 후보군(5개)이 그대로 뽑히게 한다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
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
    assert "diabetes_walk" in keys
    assert set(keys) & BASE_HABIT_KEYS


async def test_get_recommendations_drops_selected_key_no_longer_in_pool(monkeypatch):
    """당뇨 습관(diabetes_walk)을 선택해둔 뒤 진단을 다른 질환으로 바꾸면(풀이 바뀌면),
    더 이상 오늘 고를 수 없는 옛 선택 키는 selected_keys에서 빠져야 한다 - 안 그러면 프론트가
    그 유령 키를 그대로 저장 요청에 다시 실어 보내 400을 받는다(회귀 재현: 진단명별 습관이
    LLM 생성으로 바뀌면서 실제로 발생한 버그). 회전에 가려지지 않게 상한을 넉넉히 늘린다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
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


async def test_select_habits_then_today_returns_only_selected(monkeypatch):
    """추천 중 1개(walk)만 골라 선택하면, /habits/today엔 그 1개만 나와야 한다. 회전에 가려지지
    않게 상한을 넉넉히 늘려 walk가 항상 오늘의 추천 목록에 있게 한다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
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


async def test_select_habits_replaces_previous_selection(monkeypatch):
    """다시 선택하면 이전 선택은 사라지고 새 선택으로 완전히 교체돼야 한다. 회전에 가려지지
    않게 상한을 넉넉히 늘린다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_select_replace@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post("/api/v1/habits/selections", json={"habit_keys": ["water", "walk"]}, headers=headers)
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["walk"]}, headers=headers)
        response = await client.get("/api/v1/habits/today", headers=headers)

    keys = [h["key"] for h in response.json()["habits"]]
    assert keys == ["walk"]


async def test_check_habit_increments_progress_and_caps_at_target(monkeypatch):
    """선택한 습관을 체크할 때마다 진행량이 1씩 늘고, 목표치를 넘어서 더 체크해도
    target 이상으로 올라가지 않는다. 회전에 가려지지 않게 상한을 넉넉히 늘린다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_check@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/habits/selections", json={"habit_keys": ["morning_stretch"]}, headers=headers)

        for _ in range(2):  # target(1)보다 한 번 더 클릭
            response = await client.post("/api/v1/habits/today/morning_stretch/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    stretch = next(h for h in response.json()["habits"] if h["key"] == "morning_stretch")
    assert stretch["progress"] == 1
    assert stretch["completed"] is True


async def test_check_habit_with_unknown_key_returns_404():
    """오늘 선택하지 않은(또는 애초에 존재하지 않는) habit_key로 체크하면 404여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_unknown@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post("/api/v1/habits/today/diabetes_walk/check", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_all_completed_becomes_true_once_every_selected_habit_hits_target(monkeypatch):
    """선택한 습관을 각자 목표치까지 채우면 all_completed가 true가 되어야 한다(칭찬 화면 트리거).
    target=1인 습관 2개를 써서 체크 횟수를 최소화한다. 회전에 가려지지 않게 상한을 늘린다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_all_done@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(
            "/api/v1/habits/selections",
            json={"habit_keys": ["morning_stretch", "early_sleep"]},
            headers=headers,
        )

        await client.post("/api/v1/habits/today/morning_stretch/check", headers=headers)
        response = await client.post("/api/v1/habits/today/early_sleep/check", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["all_completed"] is True


def test_pick_recommendations_no_disease_rotates_without_consecutive_day_repeats():
    """질병 미등록이면 BASE_HABITS를 날짜 기준으로 회전하는데, 연속된 이틀이 완전히 똑같은
    5개로 겹치는 일이 없어야 한다(해시 나머지 방식의 알려진 결함 재발 방지 회귀 테스트).
    질병 미등록 분기는 habit_to_disease가 비어있을 때 전역 BASE_HABITS를 쓰므로 pool 내용은
    무관하다."""
    day1 = pick_recommendations([], profile_id=42, today=date(2026, 7, 14), habit_to_disease={})
    day2 = pick_recommendations([], profile_id=42, today=date(2026, 7, 15), habit_to_disease={})

    assert len(day1) == 5
    assert day1 != day2


async def test_habit_reason_feedback_accepts_and_returns_value(monkeypatch):
    """오늘의 추천 목록에 있는 habit_key로 피드백을 남기면 그대로 저장/반환돼야 한다."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_feedback_up@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )

        response = await client.post(
            "/api/v1/habits/diabetes_walk/reason-feedback", json={"value": "UP"}, headers=headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["value"] == "UP"


async def test_habit_reason_feedback_re_vote_overwrites_previous_value(monkeypatch):
    """같은 habit_key로 다시 평가하면 이전 값이 갱신돼야 한다(새 레코드가 쌓이는 게 아니라)."""
    monkeypatch.setattr(habit_service, "MAX_RECOMMENDATIONS", 20)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_feedback_revote@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.patch(
            "/api/v1/users/me/health-info",
            json={"diagnosis_history": [{"disease": "DIABETES", "detail": None}]},
            headers=headers,
        )

        await client.post("/api/v1/habits/diabetes_walk/reason-feedback", json={"value": "UP"}, headers=headers)
        response = await client.post(
            "/api/v1/habits/diabetes_walk/reason-feedback",
            json={"value": "DOWN", "comment": "이유가 와닿지 않아요"},
            headers=headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["value"] == "DOWN"


async def test_habit_reason_feedback_rejects_habit_key_not_in_todays_recommendations():
    """오늘의 추천 목록에 없는 habit_key로 피드백을 남기려 하면 404여야 한다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "habit_feedback_invalid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/habits/diabetes_walk/reason-feedback", json={"value": "UP"}, headers=headers
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
