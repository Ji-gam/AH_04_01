import httpx

from app.services import medication_open_api_client, medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


class _FakeDurDrugRepository:
    """마스터 데이터에 아무것도 없는 것처럼 가장해, Tier3(공공 API)/AUTO_ 더미 경로만 타게 한다."""

    async def search_item_names(self, session, item_name: str, limit: int) -> list[tuple[str, str]]:
        return []

    async def search_item_names_by_prefix(self, session, prefix: str, limit: int) -> list[tuple[str, str]]:
        return []


async def test_unmatched_drug_uses_public_api_item_seq_when_available(monkeypatch):
    """마스터 데이터에 없는 약이어도 Tier 3(공공 API)에서 품목기준코드를 찾으면
    AUTO_ 더미가 아니라 그 item_seq로 매칭돼야 한다."""

    async def _fake_pill(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "DRUG_SHAPE": "원형", "COLOR_CLASS1": "하양", "PRINT_FRONT": "ABC"}]

    async def _fake_approval(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "ITEM_INGR_NAME": "Acetaminophen"}]

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemSeq": "200000001", "useMethodQesitm": "1회 1정", "seQesitm": "주의사항 텍스트"}]

    async def _fake_dur(item_seq=None, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _fake_pill)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _fake_approval)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_dur)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session, _FakeDurDrugRepository(), [OcrField(text="*낫모르는약100mg", confidence=0.9)], "*낫모르는약100mg"
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq not in auto_created_ids
    assert match_confidence[drug.item_seq] == 0.9
    assert drug.item_seq == "200000001"


async def test_unmatched_drug_falls_back_to_auto_dummy_when_public_api_has_no_data(monkeypatch):
    """Tier 3 API도 데이터를 못 찾으면 기존 AUTO_ 더미 생성 폴백이 그대로 동작해야 한다."""

    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _empty)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _ = await medication_service._match_or_create_medications(
            session,
            _FakeDurDrugRepository(),
            [OcrField(text="*아무데이터도없는약999mg", confidence=0.9)],
            "*아무데이터도없는약999mg",
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq in auto_created_ids
    assert drug.item_seq.startswith("AUTO_")


async def test_unmatched_drug_falls_back_to_auto_dummy_when_public_api_times_out(monkeypatch):
    """Tier 3 API 호출이 httpx.HTTPError(타임아웃 포함)로 실패해도 등록 자체는 막히지 않아야 한다.
    (#138: 이 예외가 안 잡히면 OCR job이 processing에 영구 멈춘다)"""

    async def _raise(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _raise)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _ = await medication_service._match_or_create_medications(
            session, _FakeDurDrugRepository(), [OcrField(text="*타임아웃약700mg", confidence=0.9)], "*타임아웃약700mg"
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq in auto_created_ids
    assert drug.item_seq.startswith("AUTO_")


async def test_unmatched_drug_falls_back_to_auto_dummy_when_public_api_errors(monkeypatch):
    """Tier 3 API 호출이 실패(PublicDataApiError)해도 등록 자체는 막히지 않아야 한다."""

    async def _raise(*args, **kwargs):
        raise medication_open_api_client.PublicDataApiError("boom")

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _raise)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _raise)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _ = await medication_service._match_or_create_medications(
            session, _FakeDurDrugRepository(), [OcrField(text="*API장애약500mg", confidence=0.9)], "*API장애약500mg"
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq in auto_created_ids
    assert drug.item_seq.startswith("AUTO_")
