"""T-MED-2-2: 등록약 간 병용금기(약물 상호작용) 체크.

가짜 리포지토리로 `MedicationService.check_interactions`를 단위 테스트하고,
`/medications/interactions` 엔드포인트는 실제 DB(MySQL)로 통합 테스트한다.
`medication_open_api_client.fetch_dur_item_info`는 monkeypatch로 대체해 실제 공공데이터
API를 호출하지 않는다.
"""

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import Medication, MedicationSchedule
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client
from app.services.medication_service import MedicationService
from app.tests.conftest import TestSessionLocal
from app.tests.medication_apis.test_medication_apis import _signup_and_login


class _FakeRepository:
    def __init__(self, schedules: list[MedicationSchedule]) -> None:
        self._schedules = schedules

    async def list_schedules_by_profile(self, session, profile_id):
        return self._schedules


def _schedule(medication: Medication) -> MedicationSchedule:
    schedule = MedicationSchedule(medication_id=medication.id, times=["09:00"])
    schedule.medication = medication
    return schedule


def _medication(med_id: int, name: str, item_seq: str | None) -> Medication:
    return Medication(
        id=med_id,
        medication_name=name,
        standard_code=f"PDP_{item_seq}" if item_seq else None,
    )


async def test_no_warnings_when_fewer_than_two_medications_have_item_seq(monkeypatch):
    async def _fail_fetch(*args, **kwargs):
        raise AssertionError("비교할 다른 약이 없으면 DUR API를 호출하면 안 된다")

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fail_fetch)

    med = _medication(1, "타이레놀정", "111")
    repository = _FakeRepository([_schedule(med)])
    service = MedicationService(repository=repository)

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.warnings == []
    assert result.checked_count == 1


async def test_warns_when_registered_pair_matches_by_mixture_item_seq(monkeypatch):
    med_a = _medication(1, "타이레놀정", "111")
    med_b = _medication(2, "와파린정", "222")
    repository = _FakeRepository([_schedule(med_a), _schedule(med_b)])
    service = MedicationService(repository=repository)

    async def _fake_fetch(item_seq: str):
        if item_seq == "111":
            return [
                {
                    "MIXTURE_ITEM_SEQ": "222",
                    "MIXTURE_ITEM_NAME": "와파린정",
                    "PROHBT_CONTENT": "출혈 위험이 증가할 수 있습니다.",
                }
            ]
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_fetch)

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.checked_count == 2
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert {warning.drug_a_name, warning.drug_b_name} == {"타이레놀정", "와파린정"}
    assert warning.description == "출혈 위험이 증가할 수 있습니다."


async def test_does_not_warn_when_mixture_partner_is_not_registered(monkeypatch):
    med_a = _medication(1, "타이레놀정", "111")
    med_c = _medication(3, "이부프로펜정", "333")
    repository = _FakeRepository([_schedule(med_a), _schedule(med_c)])
    service = MedicationService(repository=repository)

    async def _fake_fetch(item_seq: str):
        if item_seq == "111":
            return [
                {
                    "MIXTURE_ITEM_SEQ": "999",
                    "MIXTURE_ITEM_NAME": "등록 안 된 약",
                    "PROHBT_CONTENT": "상관없는 경고",
                }
            ]
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_fetch)

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.warnings == []


async def test_skips_medications_without_item_seq_without_crashing(monkeypatch):
    med_no_seq = _medication(1, "이름만있는약", None)
    med_b = _medication(2, "와파린정", "222")
    repository = _FakeRepository([_schedule(med_no_seq), _schedule(med_b)])
    service = MedicationService(repository=repository)

    async def _fail_fetch(*args, **kwargs):
        raise AssertionError("item_seq가 하나뿐이면(비교 대상 부족) DUR API를 호출하면 안 된다")

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fail_fetch)

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.warnings == []
    assert result.checked_count == 1


async def test_deduplicates_warning_for_reverse_pair(monkeypatch):
    med_a = _medication(1, "타이레놀정", "111")
    med_b = _medication(2, "와파린정", "222")
    repository = _FakeRepository([_schedule(med_a), _schedule(med_b)])
    service = MedicationService(repository=repository)

    async def _fake_fetch(item_seq: str):
        if item_seq == "111":
            return [{"MIXTURE_ITEM_SEQ": "222", "MIXTURE_ITEM_NAME": "와파린정", "PROHBT_CONTENT": "경고 A"}]
        if item_seq == "222":
            return [{"MIXTURE_ITEM_SEQ": "111", "MIXTURE_ITEM_NAME": "타이레놀정", "PROHBT_CONTENT": "경고 B"}]
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_fetch)

    result = await service.check_interactions(session=None, profile_id=1)

    assert len(result.warnings) == 1


async def test_interactions_endpoint_returns_warning_for_registered_pdp_pair(monkeypatch):
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        med_a = await repo.create_medication(
            session, Medication(standard_code="PDP_111222333", medication_name="테스트타이레놀정")
        )
        med_b = await repo.create_medication(
            session, Medication(standard_code="PDP_444555666", medication_name="테스트와파린정")
        )

    async def _fake_fetch(item_seq: str):
        if item_seq == "111222333":
            return [
                {
                    "MIXTURE_ITEM_SEQ": "444555666",
                    "MIXTURE_ITEM_NAME": "테스트와파린정",
                    "PROHBT_CONTENT": "출혈 위험 증가",
                }
            ]
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_fetch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "interaction_endpoint_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/v1/medications", headers=headers, json={"drug_code": med_a.standard_code, "times": ["09:00"]}
        )
        await client.post(
            "/api/v1/medications", headers=headers, json={"drug_code": med_b.standard_code, "times": ["09:00"]}
        )

        response = await client.get("/api/v1/medications/interactions", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["checked_count"] == 2
    assert len(data["warnings"]) == 1
    assert {data["warnings"][0]["drug_a_name"], data["warnings"][0]["drug_b_name"]} == {
        "테스트타이레놀정",
        "테스트와파린정",
    }


async def test_interactions_endpoint_returns_empty_without_enough_registered_meds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "interaction_empty_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/medications/interactions", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["warnings"] == []
