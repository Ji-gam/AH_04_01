"""(#108) MySQL(Tier2) 캐시에 없는 약도 로컬 Tier1 SQLite 마스터 DB(27,000여 개,
app/database/dur_drug_light.db)에서 찾아 매칭/캐싱하는지 확인한다. 실제 SQLite 파일
내용에 의존하지 않도록 `DurDrugRepository`를 가짜 구현으로 교체해 결정적으로 검증한다."""

from app.repositories.medication_repository import MedicationRepository
from app.services import medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


class _FakeDurDrugRepository:
    """실제 SQLite 대신, 테스트가 통제하는 (item_seq, item_name) 목록만 돌려준다."""

    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    def search_item_names(self, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    def search_item_names_by_prefix(self, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]


def _patch_dur_repo(monkeypatch, items: list[tuple[str, str]]):
    monkeypatch.setattr(medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository(items))


async def test_exact_tier1_match_caches_into_mysql_with_pdp_code(monkeypatch):
    """MySQL에 없는 약이어도 Tier1에 정확히 같은 이름이 있으면, AUTO_ 더미 대신 그 약을
    PDP_{item_seq} 코드로 MySQL에 캐싱해서 매칭돼야 한다."""
    _patch_dur_repo(monkeypatch, [("209900001", "노스판패취10㎍/h")])
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="*노스판패취10㎍/h", confidence=0.9)]
        )

    assert len(matched) == 1
    med = matched[0]
    assert med.standard_code == "PDP_209900001"
    assert med.id not in auto_created_ids, "Tier1에서 찾은 약은 AUTO_ 더미가 아니다"


async def test_exact_tier1_match_reuses_cached_medication_on_second_call(monkeypatch):
    """같은 Tier1 약이 두 번 조회되면, PDP_{item_seq} 코드로 캐싱된 레코드를 재사용해야
    한다 — 매번 새 레코드를 만들면 중복이 쌓인다."""
    _patch_dur_repo(monkeypatch, [("209900002", "위더스세파클러캡슐250mg")])
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        first, _auto1, _conf1 = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="*위더스세파클러캡슐250mg", confidence=0.9)]
        )
        second, _auto2, _conf2 = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="*위더스세파클러캡슐250mg", confidence=0.9)]
        )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id


async def test_fuzzy_tier1_match_rescues_misread_text_not_in_mysql(monkeypatch):
    """(#106+#108) MySQL 퍼지 후보에도 없고 정확일치도 없는 OCR 오인식 텍스트가, Tier1
    SQLite에서는 유사도로 구제돼야 한다."""
    _patch_dur_repo(monkeypatch, [("209900003", "노스판패취10㎍/h")])
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session,
            repo,
            [
                OcrField(text="노스판매취10ug/h", confidence=0.7),  # "패취"→"매취" 오인식
                OcrField(text="[한국먼디파마]", confidence=0.7),
            ],
        )

    assert len(matched) == 1
    med = matched[0]
    assert med.standard_code == "PDP_209900003"
    assert med.id not in auto_created_ids
    assert match_confidence[med.id] == 0.7


async def test_tier1_no_match_falls_through_without_error(monkeypatch):
    """Tier1에도 없는 완전히 새로운 약은 기존처럼 AUTO_ 더미 생성으로 계속 이어져야 한다."""
    _patch_dur_repo(monkeypatch, [])
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="*완전히새로운약999mg", confidence=0.9)]
        )

    assert len(matched) == 1
    assert matched[0].id in auto_created_ids


async def test_search_medications_includes_tier1_only_drug(monkeypatch):
    """ "더보기 > 약품 검색"이 참조하는 것과 같은 Tier1 SQLite에만 있고 MySQL(Tier2)엔 아직
    없는 약도, 수동 등록 검색 자동완성(search_medications)의 결과에 포함돼야 한다."""
    _patch_dur_repo(monkeypatch, [("309900001", "타이레놀정500mg")])
    service = medication_service.MedicationService()

    async with TestSessionLocal() as session:
        results = await service.search_medications(session, "타이레놀")

    assert len(results) == 1
    assert results[0]["standard_code"] == "PDP_309900001"
    assert results[0]["medication_name"] == "타이레놀정500mg"


async def test_search_medications_does_not_duplicate_medication_already_in_mysql(monkeypatch):
    """같은 약이 MySQL에 이미 있고 Tier1 검색 결과에도 잡히면, 한 번만 나와야 한다."""
    repo = MedicationRepository()
    async with TestSessionLocal() as session:
        existing = await repo.create_medication(
            session, medication_service.Medication(medication_name="타이레놀정500mg", standard_code="PDP_309900002")
        )
        _patch_dur_repo(monkeypatch, [("309900002", "타이레놀정500mg")])
        service = medication_service.MedicationService()

        results = await service.search_medications(session, "타이레놀")

    assert len(results) == 1
    assert results[0]["id"] == existing.id
