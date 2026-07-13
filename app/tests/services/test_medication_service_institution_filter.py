"""약국/병원명이 OCR 텍스트에 "*" 불릿과 함께 섞여 있어도("SAMPLE*약국" 등) 약품 후보로
잡히거나 마스터 DB에 즉석 생성되면 안 된다 — 처방전 헤더의 약국명을 실제 약으로 오인해
등록해버리는 회귀를 방지한다."""

from app.models.medication_model import Medication
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
    monkeypatch.setattr(medication_service, "DurDrugRepository", lambda: _FakeDurDrugRepository([("1", "필독정")]))
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        matched, _auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, repo, [OcrField(text="필독약국", confidence=1.0)]
        )

    assert matched == []


async def test_institution_name_with_trailing_particle_is_not_fuzzy_matched():
    """(#120) "본 약국의 의견과는..." 같은 실제 처방전 문구에서 조사가 붙은 "약국의"는 문자열
    끝이 "약국"으로 끝나지 않는다 — 끝 앵커만으로 걸러내면 이런 필드가 새 나가, 예전 버그로
    이미 DB에 남아있는 쓰레기 레코드("SAMPLE*약국" 등)와 유사도 매칭돼버리는 회귀를 방지한다.
    (top-3 "근거 없음" 폴백이 결과를 가릴 수 있어 `_fuzzy_match_unrecognized_fields`를 직접 호출한다.)"""
    repo = MedicationRepository()

    async with TestSessionLocal() as session:
        stale = await repo.create_medication(
            session, Medication(medication_name="SAMPLE*약국", standard_code="AUTO_TEST_STALE")
        )

        matched, _confidences = await medication_service._fuzzy_match_unrecognized_fields(
            session, repo, [OcrField(text="약국의", confidence=0.99)], set()
        )

    assert stale.id not in {med.id for med in matched}


class _FakeDurDrugRepository:
    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    def search_item_names(self, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    def search_item_names_by_prefix(self, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]
