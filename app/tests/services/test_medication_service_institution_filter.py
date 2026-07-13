"""약국/병원명이 OCR 텍스트에 "*" 불릿과 함께 섞여 있어도("SAMPLE*약국" 등) 약품 후보로
잡히거나 마스터 DB에 즉석 생성되면 안 된다 — 처방전 헤더의 약국명을 실제 약으로 오인해
등록해버리는 회귀를 방지한다."""

from app.repositories.medication_repository import MedicationRepository
from app.services import medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


async def test_institution_name_with_bullet_is_not_registered_as_medication(monkeypatch):
    monkeypatch.setattr(medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository([]))
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="*SAMPLE*약국", confidence=1.0)]
        )

    assert matched == []
    assert auto_created_ids == set()


async def test_institution_name_without_bullet_is_not_fuzzy_matched(monkeypatch):
    monkeypatch.setattr(
        medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository([("1", "필독정")])
    )
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, _auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="필독약국", confidence=1.0)]
        )

    assert matched == []


class _FakeDurDrugRepository:
    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    def search_item_names(self, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    def search_item_names_by_prefix(self, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]
