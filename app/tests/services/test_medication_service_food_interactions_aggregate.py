"""T-DOC-2: 등록약 전체 기준 음식/음주 주의사항 체크(`check_food_interactions`).

가짜 리포지토리로 서비스 레이어를 단위 테스트하고, `/medications/food-interactions`
엔드포인트는 실제 DB(MySQL)로 통합 테스트한다. `medication_open_api_client.fetch_drug_summary`는
monkeypatch로 대체해 실제 공공데이터 API를 호출하지 않는다.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import Medication, MedicationSchedule
from app.services import medication_open_api_client
from app.services.medication_service import MedicationService
from app.tests.medication_apis.test_medication_apis import _seed_dummy_medications, _signup_and_login


class _FakeRepository:
    def __init__(self, schedules: list[MedicationSchedule]) -> None:
        self._schedules = schedules

    async def list_schedules_by_profile(self, session, profile_id):
        return self._schedules


def _schedule(medication: Medication) -> MedicationSchedule:
    schedule = MedicationSchedule(medication_id=medication.id, times=["09:00"])
    schedule.medication = medication
    return schedule


def _medication(med_id: int, name: str) -> Medication:
    return Medication(id=med_id, medication_name=name)


async def test_returns_empty_result_when_no_registered_medications():
    repository = _FakeRepository([])
    service = MedicationService(repository=repository)

    result = await service.check_food_interactions(session=None, profile_id=1)

    assert result.guide_cards == []
    assert result.checked_count == 0


async def test_dedupes_multiple_schedules_of_same_medication(monkeypatch):
    calls: list[str] = []

    async def _fake_summary(item_name=None, **kwargs):
        calls.append(item_name)
        return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    med = _medication(1, "타이레놀정")
    # 같은 약을 여러 시간대로 등록해도(스케줄 2개) 조회는 약 단위로 한 번만 해야 한다.
    repository = _FakeRepository([_schedule(med), _schedule(med)])
    service = MedicationService(repository=repository)

    result = await service.check_food_interactions(session=None, profile_id=1)

    assert calls == ["타이레놀정"]
    assert result.checked_count == 1
    assert len(result.guide_cards) == 1
    assert "자몽주스" in result.guide_cards[0].content


async def test_reports_unavailable_card_when_api_fails_but_keeps_others(monkeypatch):
    """한 약의 API 호출이 실패해도 다른 약은 정상 카드가 나오고, 실패한 약도 카드 자체는
    사라지지 않고 '확인 불가'로 명시돼야 한다 — 카드가 없으면 그 약은 검사 안 한 것처럼 보임."""

    async def _fake_summary(item_name=None, **kwargs):
        if item_name == "실패약":
            raise medication_open_api_client.PublicDataApiError("boom")
        return [{"itemName": item_name, "intrcQesitm": "우유와 함께 복용하지 마세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    med_ok = _medication(1, "정상약")
    med_fail = _medication(2, "실패약")
    repository = _FakeRepository([_schedule(med_ok), _schedule(med_fail)])
    service = MedicationService(repository=repository)

    result = await service.check_food_interactions(session=None, profile_id=1)

    assert result.checked_count == 2
    assert len(result.guide_cards) == 2
    ok_card = next(c for c in result.guide_cards if "정상약" in c.title)
    fail_card = next(c for c in result.guide_cards if "실패약" in c.title)
    assert "우유" in ok_card.content
    assert ok_card.severity == "caution"
    assert "찾지 못해" in fail_card.content
    assert fail_card.severity == "info"


async def test_food_interactions_endpoint_returns_guide_cards_for_registered_medications(monkeypatch):
    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    await _seed_dummy_medications()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "food_interaction_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/v1/medications",
            headers=headers,
            json={"drug_code": "KD_T3001", "times": ["09:00"]},
        )

        response = await client.get("/api/v1/medications/food-interactions", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["checked_count"] == 1
        assert len(data["guide_cards"]) == 1
        assert "자몽주스" in data["guide_cards"][0]["content"]


async def test_food_interactions_endpoint_returns_empty_when_no_registered_medications():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "no_meds_food_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/medications/food-interactions", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["checked_count"] == 0
        assert data["guide_cards"] == []
