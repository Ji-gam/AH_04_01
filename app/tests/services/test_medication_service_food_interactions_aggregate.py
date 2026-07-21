"""T-DOC-2/T-DOC-5: 등록약 전체 기준 음식/음주 주의사항 체크.

`/medications/food-interactions`(빠른 응답, `check_food_interactions`)는 식약처 참조 테이블과
MySQL `drugs_data` 스냅샷만 사용해 실시간 API를 호출하지 않는다. 두 단계로 확인되지 않은 약은
`pending_medication_names`로 넘어가고, `/medications/food-interactions/pending`
(`check_food_interactions_pending`)이 그 약들만 실시간 e약은요 API로 확인한다.

가짜 리포지토리로 서비스 레이어를 단위 테스트하고, `/medications/food-interactions`
엔드포인트는 실제 DB(MySQL)로 통합 테스트한다. `medication_open_api_client.fetch_drug_summary`와
`DurDrugRepository.find_food_intrc_text`는 monkeypatch로 대체해 실제 공공데이터 API/운영 시딩
데이터를 참조하지 않고 결정적으로 동작하게 한다.
"""

from typing import cast

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app
from app.models.medication_model import MedicationSchedule
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client
from app.services.medication_service import MedicationService
from app.tests.medication_apis.test_medication_apis import _seed_dummy_medications, _signup_and_login


def _no_local_snapshot_match(monkeypatch):
    """(T-DOC-5) 참조 테이블 밖 약은 전부 MySQL `drugs_data` 스냅샷(2단계)에도 없다고 가정해,
    fast tier가 항상 `pending`으로 넘기게 만든다 — 실제 운영 시딩 데이터(`seed_dur`) 내용과
    무관하게 결정적으로 테스트하기 위함이며, `session=None`으로 호출하는 단위 테스트들이
    실제 DB 쿼리를 타지 않게(=크래시하지 않게) 하는 목적도 겸한다."""

    async def _fake_find(self, session, item_name):
        return None

    monkeypatch.setattr(DurDrugRepository, "find_food_intrc_text", _fake_find)


class _FakeRepository:
    def __init__(self, schedules: list[MedicationSchedule]) -> None:
        self._schedules = schedules

    async def list_schedules_by_profile(self, session, profile_id):
        return self._schedules


class _FakeDurDrugRepository:
    """(T-MED-16) 이 단위 테스트들은 스케줄에 이미 `display_name`을 채워서 이름 해석이 필요
    없으므로, 아무것도 반환하지 않는 가짜 구현으로 `get_names_by_item_seqs`의 실제 DB 조회를
    피한다(세션이 None이라 실제 조회를 하면 바로 에러가 난다)."""

    async def get_names_by_item_seqs(self, session, item_seqs):
        return {}


def _schedule(item_seq: str, name: str) -> MedicationSchedule:
    return MedicationSchedule(item_seq=item_seq, display_name=name, times=["09:00"])


def _service(schedules: list[MedicationSchedule]) -> MedicationService:
    return MedicationService(
        repository=cast(MedicationRepository, _FakeRepository(schedules)),
        dur_drug_repository=cast(DurDrugRepository, _FakeDurDrugRepository()),
    )


async def test_returns_empty_result_when_no_registered_medications():
    service = _service([])

    result = await service.check_food_interactions(session=None, profile_id=1)

    assert result.guide_cards == []
    assert result.checked_count == 0
    assert result.pending_medication_names == []


async def test_fast_check_does_not_call_live_api_and_defers_unresolved_to_pending(monkeypatch):
    """(T-DOC-5) 빠른 응답(`check_food_interactions`)은 참조 테이블/MySQL 스냅샷으로 확인 안
    되는 약이 있어도 실시간 API를 호출하지 않고, 그 약 이름만 `pending_medication_names`에 담아
    돌려줘야 한다."""
    _no_local_snapshot_match(monkeypatch)
    calls: list[str] = []

    async def _fake_summary(item_name=None, **kwargs):
        calls.append(item_name)
        return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    # 같은 약을 여러 시간대로 등록해도(스케줄 2개) 조회는 약 단위로 한 번만 해야 한다.
    service = _service([_schedule("1", "타이레놀정"), _schedule("1", "타이레놀정")])

    result = await service.check_food_interactions(session=None, profile_id=1)

    assert calls == []
    assert result.checked_count == 1
    assert result.guide_cards == []
    assert result.pending_medication_names == ["타이레놀정"]


async def test_pending_check_dedupes_multiple_schedules_of_same_medication(monkeypatch):
    """(T-DOC-5) `check_food_interactions_pending`은 fast tier로 확인 안 된 약만 실시간
    API로 조회하며, 같은 약을 여러 시간대로 등록해도(스케줄 2개) 조회는 약 단위로 한 번만 한다."""
    _no_local_snapshot_match(monkeypatch)
    calls: list[str] = []

    async def _fake_summary(item_name=None, **kwargs):
        calls.append(item_name)
        return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    service = _service([_schedule("1", "타이레놀정"), _schedule("1", "타이레놀정")])

    result = await service.check_food_interactions_pending(session=None, profile_id=1)

    assert calls == ["타이레놀정"]
    assert len(result.guide_cards) == 1
    assert "자몽주스" in result.guide_cards[0].content


async def test_pending_check_reports_unavailable_card_when_api_fails_but_keeps_others(monkeypatch):
    """한 약의 API 호출이 실패해도 다른 약은 정상 카드가 나오고, 실패한 약도 카드 자체는
    사라지지 않고 '확인 불가'로 명시돼야 한다 — 카드가 없으면 그 약은 검사 안 한 것처럼 보임."""
    _no_local_snapshot_match(monkeypatch)

    async def _fake_summary(item_name=None, **kwargs):
        if item_name == "실패약":
            raise medication_open_api_client.PublicDataApiError("boom")
        return [{"itemName": item_name, "intrcQesitm": "우유와 함께 복용하지 마세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    service = _service([_schedule("1", "정상약"), _schedule("2", "실패약")])

    result = await service.check_food_interactions_pending(session=None, profile_id=1)

    assert len(result.guide_cards) == 2
    ok_card = next(c for c in result.guide_cards if "정상약" in c.title)
    fail_card = next(c for c in result.guide_cards if "실패약" in c.title)
    assert "우유" in ok_card.content
    assert ok_card.severity == "caution"
    assert "찾지 못해" in fail_card.content
    assert fail_card.severity == "info"


async def test_pending_check_sorts_caution_cards_before_info_cards(monkeypatch):
    """(T-DOC-3) 실제 주의사항이 있는 카드(severity="caution")가 "확인 안 됨"/"주의사항 없음"
    카드(severity="info")보다 앞에 오도록 정렬해야 한다 — 등록약이 많으면 실제로 봐야 할 카드가
    뒤로 밀려 놓치기 쉽다. 원래 등록 순서상 정보 없음(info) → 정보 없음(info) → 실제 주의사항
    있음(caution) 순으로 두어도, 결과는 caution이 앞으로 와야 한다."""
    _no_local_snapshot_match(monkeypatch)

    async def _fake_summary(item_name=None, **kwargs):
        if item_name == "실제주의사항약":
            return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    service = _service([_schedule("1", "정보없는약1"), _schedule("2", "정보없는약2"), _schedule("3", "실제주의사항약")])

    result = await service.check_food_interactions_pending(session=None, profile_id=1)

    assert [c.severity for c in result.guide_cards] == ["caution", "info", "info"]
    assert "실제주의사항약" in result.guide_cards[0].title


async def test_food_interactions_endpoint_returns_pending_medication_when_unresolved(monkeypatch):
    """빠른 엔드포인트는 참조 테이블/MySQL 스냅샷으로 확인 안 되는 등록약을
    `pending_medication_names`로 넘기고, 느린 엔드포인트가 실시간 API로 그 약을 채운다."""
    _no_local_snapshot_match(monkeypatch)

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)
    _seed_dummy_medications(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "food_interaction_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await client.post(
            "/api/v1/medications",
            headers=headers,
            json={"drug_code": "KD_T3001", "times": ["09:00"]},
        )

        fast_response = await client.get("/api/v1/medications/food-interactions", headers=headers)
        assert fast_response.status_code == status.HTTP_200_OK
        fast_data = fast_response.json()
        assert fast_data["checked_count"] == 1
        assert fast_data["guide_cards"] == []
        assert len(fast_data["pending_medication_names"]) == 1

        pending_response = await client.get("/api/v1/medications/food-interactions/pending", headers=headers)
        assert pending_response.status_code == status.HTTP_200_OK
        pending_data = pending_response.json()
        assert len(pending_data["guide_cards"]) == 1
        assert "자몽주스" in pending_data["guide_cards"][0]["content"]


async def test_food_interactions_endpoint_returns_empty_when_no_registered_medications():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_and_login(client, "no_meds_food_test@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/medications/food-interactions", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["checked_count"] == 0
        assert data["guide_cards"] == []
        assert data["pending_medication_names"] == []
