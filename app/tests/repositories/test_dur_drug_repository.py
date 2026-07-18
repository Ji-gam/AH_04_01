"""
T-LLM-2-dur-repository: `app/models/dur.py`(MySQL, `app/scripts/seed_dur.py`가 실제
`drugs_full.db`에서 시딩 - `app/tests/conftest.py`) 조회 로직을 검증한다.

T-LLM-2-drug-gateway: `drug_data()` 캐스케이드(MySQL 1단계 → MySQL 캐시 → 외부 API)는
테스트 MySQL(`TestSessionLocal`)을 대상으로 검증하고, 외부 API만
`drug_public_api_client.fetch_drug_summary`를 monkeypatch한다.
"""

import pytest
from sqlalchemy import select

from app.models.drug_data_cache_model import DrugDataCache
from app.repositories.dur_drug_repository import DrugDataProvenance, DurDrugRepository
from app.services import drug_public_api_client
from app.tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

repository = DurDrugRepository()


async def test_find_drug_info_returns_profile_for_matching_product():
    async with TestSessionLocal() as session:
        profiles = await repository.find_drug_info(session, "활명수")

    assert len(profiles) >= 1
    assert any(p.efficacy is not None for p in profiles)


async def test_find_drug_info_returns_empty_list_for_unknown_product():
    async with TestSessionLocal() as session:
        profiles = await repository.find_drug_info(session, "존재하지않는의약품이름12345")

    assert profiles == []


async def test_find_dur_warnings_returns_pregnancy_warning_for_known_teratogen():
    async with TestSessionLocal() as session:
        warnings = await repository.find_dur_warnings(session, "테라싸이클린", pregnant=True, geriatric=False)

    assert any("임부금기" in w for w in warnings)


async def test_find_dur_warnings_returns_empty_when_no_risk_flags():
    async with TestSessionLocal() as session:
        warnings = await repository.find_dur_warnings(session, "테라싸이클린", pregnant=False, geriatric=False)

    assert warnings == []


async def test_find_dur_warnings_returns_empty_for_unknown_product():
    async with TestSessionLocal() as session:
        warnings = await repository.find_dur_warnings(
            session, "존재하지않는의약품이름12345", pregnant=True, geriatric=True
        )

    assert warnings == []


async def test_drug_data_returns_sqlite_result_when_content_is_sufficient():
    async with TestSessionLocal() as session:
        result = await repository.drug_data(session, "활명수")

    assert result.provenance == DrugDataProvenance.SQLITE
    assert any(p.efficacy for p in result.profiles)


async def test_drug_data_falls_back_to_api_and_merges_when_sqlite_content_insufficient(monkeypatch):
    """'테라싸이클린...'은 1단계에 DUR규칙/성분은 있지만 효능 텍스트가 없는 제품(기존
    test_find_dur_warnings 테스트와 동일 제품) — API 폴백 + 필드 병합을 검증하기 좋은 픽스처."""
    drug_name_in_db = "테라싸이클린캅셀250밀리그람(염산테트라싸이클린)"

    async def _fake_summary(item_name: str) -> list[dict]:
        return [
            {
                "itemName": drug_name_in_db,
                "entpName": "테스트제약",
                "efcyQesitm": "세균 감염증 치료",
                "useMethodQesitm": "1일 1회 복용",
                "atpnQesitm": "임부 금기",
                "seQesitm": "구역, 구토",
            }
        ]

    monkeypatch.setattr(drug_public_api_client, "fetch_drug_summary", _fake_summary)

    async with TestSessionLocal() as session:
        result = await repository.drug_data(session, "테라싸이클린")

    assert result.provenance == DrugDataProvenance.API
    merged = next(p for p in result.profiles if p.item_name == drug_name_in_db)
    assert merged.efficacy == "세균 감염증 치료"
    assert merged.dur_rules  # 1단계 전용 필드는 병합 후에도 보존
    assert merged.ingredients  # 1단계 전용 필드는 병합 후에도 보존


async def test_drug_data_writes_back_api_result_to_mysql_cache(monkeypatch):
    async def _fake_summary(item_name: str) -> list[dict]:
        return [{"itemName": "존재하지않는의약품이름12345", "efcyQesitm": "효능 텍스트"}]

    monkeypatch.setattr(drug_public_api_client, "fetch_drug_summary", _fake_summary)

    async with TestSessionLocal() as session:
        await repository.drug_data(session, "존재하지않는의약품이름12345")

    async with TestSessionLocal() as session:
        cache_result = await session.execute(
            select(DrugDataCache).where(DrugDataCache.query_name == "존재하지않는의약품이름12345")
        )
        cached = cache_result.scalar_one_or_none()

    assert cached is not None
    assert cached.profiles[0]["efficacy"] == "효능 텍스트"


async def test_drug_data_second_call_hits_cache_without_calling_api_again(monkeypatch):
    call_count = 0

    async def _fake_summary(item_name: str) -> list[dict]:
        nonlocal call_count
        call_count += 1
        return [{"itemName": "캐시테스트약품", "efcyQesitm": "캐시 확인용 효능"}]

    monkeypatch.setattr(drug_public_api_client, "fetch_drug_summary", _fake_summary)

    async with TestSessionLocal() as session:
        first = await repository.drug_data(session, "캐시테스트약품")
    async with TestSessionLocal() as session:
        second = await repository.drug_data(session, "캐시테스트약품")

    assert first.provenance == DrugDataProvenance.API
    assert second.provenance == DrugDataProvenance.CACHE
    assert call_count == 1


async def test_drug_data_returns_miss_when_not_found_anywhere(monkeypatch):
    async def _empty_summary(item_name: str) -> list[dict]:
        return []

    monkeypatch.setattr(drug_public_api_client, "fetch_drug_summary", _empty_summary)

    async with TestSessionLocal() as session:
        result = await repository.drug_data(session, "완전히없는약이름999999")

    assert result.profiles == []
    assert result.provenance == DrugDataProvenance.MISS


async def test_drug_data_does_not_cache_empty_api_result(monkeypatch):
    call_count = 0

    async def _empty_summary(item_name: str) -> list[dict]:
        nonlocal call_count
        call_count += 1
        return []

    monkeypatch.setattr(drug_public_api_client, "fetch_drug_summary", _empty_summary)

    async with TestSessionLocal() as session:
        await repository.drug_data(session, "완전히없는약이름999999")
    async with TestSessionLocal() as session:
        await repository.drug_data(session, "완전히없는약이름999999")

    assert call_count == 2
