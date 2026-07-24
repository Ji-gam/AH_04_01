"""(T-MED-16) 마스터 데이터(`dur_prod_master_list`, `DurDrugRepository`)를 직접 조회해 약을
매칭하는지 확인한다. 실제 시드 데이터 내용에 의존하지 않도록 `DurDrugRepository`를 가짜
구현으로 교체해 결정적으로 검증한다."""

from app.services import medication_open_api_client, medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


class _FakeDurDrugRepository:
    """실제 마스터 DB 대신, 테스트가 통제하는 (item_seq, item_name) 목록만 돌려준다."""

    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    async def search_item_names(self, session, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    async def search_item_names_by_prefix(self, session, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]

    async def get_names_by_item_seqs(self, session, item_seqs: set[str]) -> dict[str, str]:
        return {seq: name for seq, name in self._items if seq in item_seqs}


async def test_exact_master_data_match_is_used_instead_of_auto_dummy():
    """마스터 데이터에 정확히 같은 이름이 있으면, AUTO_ 더미 대신 그 item_seq로 매칭돼야 한다."""
    dur_repo = _FakeDurDrugRepository([("209900001", "노스판패취10㎍/h")])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*노스판패취10㎍/h", confidence=0.9)], "*노스판패취10㎍/h"
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq == "209900001"
    assert drug.item_seq not in auto_created_ids, "마스터 데이터에서 찾은 약은 AUTO_ 더미가 아니다"


async def test_fuzzy_match_rescues_misread_text_not_in_master_data_exactly():
    """(#106) 정확일치 후보에도 없는 OCR 오인식 텍스트가, 마스터 데이터 유사도 비교로
    구제돼야 한다."""
    dur_repo = _FakeDurDrugRepository([("209900003", "노스판패취10㎍/h")])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session,
            dur_repo,
            [
                OcrField(text="노스판매취10ug/h", confidence=0.7),  # "패취"→"매취" 오인식
                OcrField(text="[한국먼디파마]", confidence=0.7),
            ],
            "노스판매취10ug/h [한국먼디파마]",
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq == "209900003"
    assert drug.item_seq not in auto_created_ids
    assert match_confidence[drug.item_seq] == 0.7


async def test_master_data_match_with_parenthesized_ingredient_suffix_is_used():
    """(#OCR-MASTER-MATCH) 마스터 데이터의 item_name은 "브랜드명(성분/함량)" 형태로 저장된
    경우가 흔한데, OCR은 보통 괄호 밖 브랜드명까지만 인식한다. 문자열 완전일치만 요구하면
    실제로 마스터에 있는 약도 매번 Tier3 실시간 API로 새 나가므로(재현마다 새 item_seq
    발급), 후보가 유일하면 이 경우도 마스터 매치로 인정해야 한다."""
    dur_repo = _FakeDurDrugRepository([("KD_HANMI001", "한미오메가연질캡슐(오메가-3산에틸에스테르90)")])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*한미오메가연질캡슐", confidence=1.0)], "*한미오메가연질캡슐"
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq == "KD_HANMI001"
    assert drug.item_seq not in auto_created_ids


async def test_ambiguous_parenthesized_master_matches_fall_back_to_auto_dummy(monkeypatch):
    """(#OCR-MASTER-MATCH) 괄호 접미사 구제는 후보가 유일할 때만 적용한다 - 같은 브랜드명에
    성분이 다른 복수 품목이 있으면 어느 쪽인지 알 수 없으므로 섣불리 확정하지 않는다."""
    dur_repo = _FakeDurDrugRepository(
        [
            ("KD_A", "브랜드테스트약(성분1)"),
            ("KD_B", "브랜드테스트약(성분2)"),
        ]
    )

    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _empty)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*브랜드테스트약", confidence=0.9)], "*브랜드테스트약"
        )

    assert len(matched) == 1
    assert matched[0].item_seq in auto_created_ids


async def test_no_master_data_match_falls_through_to_auto_dummy_without_error():
    """마스터 데이터에도 없는 완전히 새로운 약은 AUTO_ 더미 생성으로 이어져야 한다."""
    dur_repo = _FakeDurDrugRepository([])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*완전히새로운약999mg", confidence=0.9)], "*완전히새로운약999mg"
        )

    assert len(matched) == 1
    assert matched[0].item_seq in auto_created_ids


async def test_search_medications_returns_master_data_matches(monkeypatch):
    """수동 등록 검색 자동완성(search_medications)은 마스터 데이터에서 이름으로 찾은 약을
    반환해야 한다."""
    dur_repo = _FakeDurDrugRepository([("309900001", "타이레놀정500mg")])
    monkeypatch.setattr(medication_service, "DurDrugRepository", lambda: dur_repo)
    service = medication_service.MedicationService()

    async with TestSessionLocal() as session:
        results = await service.search_medications(session, "타이레놀")

    assert len(results) == 1
    assert results[0]["item_seq"] == "309900001"
    assert results[0]["medication_name"] == "타이레놀정500mg"
