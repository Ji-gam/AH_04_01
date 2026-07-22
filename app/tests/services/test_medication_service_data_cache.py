"""T-MED-x-drug-gateway-cache: `_resolve_unmatched_name`의 Tier3(공공 API) 호출 앞에 놓인
MySQL 캐시(`medication_data_cache`)를 검증한다. T-LLM-2-drug-gateway `DurDrugRepository.drug_data()`
캐스케이드 테스트(`app/tests/repositories/test_dur_drug_repository.py`)와 동일한 패턴 —
테스트 MySQL(`TestSessionLocal`)을 대상으로 검증하고, 외부 API 4개만 monkeypatch한다."""

from app.services import medication_open_api_client, medication_service
from app.tests.conftest import TestSessionLocal


async def test_resolve_unmatched_name_second_call_hits_cache_without_calling_api_again(monkeypatch):
    call_count = 0

    async def _fake_pill(item_name=None, **kwargs):
        nonlocal call_count
        call_count += 1
        return [{"ITEM_SEQ": "300000001", "DRUG_SHAPE": "원형", "COLOR_CLASS1": "하양", "PRINT_FRONT": "ABC"}]

    async def _fake_approval(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "300000001"}]

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemSeq": "300000001", "useMethodQesitm": "1회 1정"}]

    async def _fake_dur(item_seq=None, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _fake_pill)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _fake_approval)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _fake_dur)

    async with TestSessionLocal() as session:
        first_item_seq, first_is_auto = await medication_service._resolve_unmatched_name(session, "캐시테스트약품")
    async with TestSessionLocal() as session:
        second_item_seq, second_is_auto = await medication_service._resolve_unmatched_name(session, "캐시테스트약품")

    assert call_count == 1
    assert first_item_seq == second_item_seq == "300000001"
    assert not first_is_auto
    assert not second_is_auto


async def test_resolve_unmatched_name_does_not_cache_empty_api_result(monkeypatch):
    call_count = 0

    async def _empty(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _empty)

    async with TestSessionLocal() as session:
        item_seq, is_auto = await medication_service._resolve_unmatched_name(session, "완전히없는약이름888888")
    count_after_first_call = call_count

    async with TestSessionLocal() as session:
        await medication_service._resolve_unmatched_name(session, "완전히없는약이름888888")

    # 빈 응답은 캐싱되지 않으므로, 두 번째 호출도 외부 API(낱알식별/허가정보/e약은요)를
    # 처음과 똑같이 다시 부른다 - 캐시 히트라면 call_count가 늘지 않아야 하는데, 그렇지 않다.
    assert call_count == count_after_first_call * 2
    assert is_auto
    assert item_seq.startswith("AUTO_")
