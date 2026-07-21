"""T-MED-2-2: 등록약 간 병용금기(약물 상호작용) 체크.

가짜 리포지토리로 `MedicationService.check_interactions`를 단위 테스트하고,
`/medications/interactions` 엔드포인트는 실제 DB(MySQL)로 통합 테스트한다.
`medication_open_api_client.fetch_dur_item_info`는 monkeypatch로 대체해 실제 공공데이터
API를 호출하지 않는다.

(T-MED-16) 스케줄이 이제 item_seq를 직접 들고 있어(과거 `medications` 캐시 테이블/AUTO_ 코드
백필 로직이 사라짐), 매칭되지 않는 약은 애초에 등록 시점에 AUTO_ 더미 코드를 받는다 - 조회
시점의 "표준코드 없는 약 백필" 개념 자체가 없어졌다."""

from typing import cast

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import MedicationSchedule
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client, medication_service
from app.services.medication_service import MedicationService
from app.tests.medication_apis.test_medication_apis import _FakeDurDrugRepository, _signup_and_login


class _FakeRepository:
    def __init__(self, schedules: list[MedicationSchedule]) -> None:
        self._schedules = schedules

    async def list_schedules_by_profile(self, session, profile_id):
        return self._schedules


def _schedule(item_seq: str) -> MedicationSchedule:
    return MedicationSchedule(item_seq=item_seq, times=["09:00"])


def _service(schedules: list[MedicationSchedule], names: dict[str, str]) -> MedicationService:
    return MedicationService(
        repository=cast(MedicationRepository, _FakeRepository(schedules)),
        dur_drug_repository=cast(DurDrugRepository, _FakeDurDrugRepository(list(names.items()))),
    )


async def test_no_warnings_when_fewer_than_two_medications_have_item_seq(monkeypatch):
    async def _fail_fetch(*args, **kwargs):
        raise AssertionError("비교할 다른 약이 없으면 DUR API를 호출하면 안 된다")

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fail_fetch)

    service = _service([_schedule("111")], {"111": "타이레놀정"})

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.warnings == []
    assert result.checked_count == 1


async def test_warns_when_registered_pair_matches_by_mixture_item_seq(monkeypatch):
    service = _service([_schedule("111"), _schedule("222")], {"111": "타이레놀정", "222": "와파린정"})

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
    service = _service([_schedule("111"), _schedule("333")], {"111": "타이레놀정", "333": "이부프로펜정"})

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


async def test_skips_auto_dummy_schedules_without_crashing(monkeypatch):
    """(T-MED-16) 마스터 데이터에 없어 AUTO_ 더미 코드를 받은 약은 병용금기 비교 대상에서
    빠져야 한다 - item_seq가 진짜가 아니라 DUR API에 물어볼 수 없다."""
    auto_schedule = MedicationSchedule(item_seq="AUTO_TEST123", display_name="이름만있는약", times=["09:00"])
    service = _service([auto_schedule, _schedule("222")], {"222": "와파린정"})

    async def _fail_fetch(*args, **kwargs):
        raise AssertionError("item_seq가 하나뿐이면(비교 대상 부족) DUR API를 호출하면 안 된다")

    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fail_fetch)

    result = await service.check_interactions(session=None, profile_id=1)

    assert result.warnings == []
    assert result.checked_count == 1


async def test_deduplicates_warning_for_reverse_pair(monkeypatch):
    service = _service([_schedule("111"), _schedule("222")], {"111": "타이레놀정", "222": "와파린정"})

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
    monkeypatch.setattr(
        medication_service,
        "DurDrugRepository",
        lambda: _FakeDurDrugRepository([("111222333", "테스트타이레놀정"), ("444555666", "테스트와파린정")]),
    )

    async def _always_exists(self, session, item_seq):
        return True

    monkeypatch.setattr(MedicationRepository, "item_seq_exists", _always_exists)

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

        await client.post("/api/v1/medications", headers=headers, json={"drug_code": "111222333", "times": ["09:00"]})
        await client.post("/api/v1/medications", headers=headers, json={"drug_code": "444555666", "times": ["09:00"]})

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
