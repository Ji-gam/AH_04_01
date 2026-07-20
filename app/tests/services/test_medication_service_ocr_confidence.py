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


def test_compute_match_rate_uses_confidence_directly_for_known_drug():
    """(T-MED-6) 마스터 데이터에 이미 있는 약은 하드코딩된 값(1.0/0.85) 대신 실제 OCR confidence를
    match_rate로 그대로 사용해야 한다."""
    assert medication_service._compute_match_rate(0.63, is_auto_created=False) == 0.63
    assert medication_service._compute_match_rate(0.42, is_auto_created=False) == 0.42


def test_compute_match_rate_caps_auto_created_despite_high_confidence():
    """(T-MED-6) 즉석 생성된(AUTO_) 약품은 OCR 신뢰도가 아무리 높아도 상한(0.5) 이하로 눌려야 한다."""
    assert medication_service._compute_match_rate(0.99, is_auto_created=True) == 0.5
    assert (
        medication_service._compute_match_rate(0.3, is_auto_created=True) == 0.3
    )  # 상한보다 낮은 confidence는 그대로 유지


async def test_match_or_create_medications_returns_ocr_confidence_for_existing_match():
    """(T-MED-6) `_match_or_create_medications`이 반환하는 confidence 맵이 실제 매칭에 쓰인
    OCR 필드의 confidence와 일치해야 한다."""
    dur_repo = _FakeDurDrugRepository([("KD_CONF001", "컨피던스정100mg")])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*컨피던스정100mg", confidence=0.63)]
        )

    assert any(d.item_seq == "KD_CONF001" for d in matched)
    assert "KD_CONF001" not in auto_created_ids
    assert match_confidence["KD_CONF001"] == 0.63


async def test_match_or_create_medications_reports_confidence_for_auto_created_drug(monkeypatch):
    """(T-MED-6) 마스터 데이터/공공 API 어디에도 없어 즉석 생성된 약품도 confidence 맵에 포함되어야
    한다 — 상한 적용은 `_compute_match_rate`가 담당하고, 이 함수는 원본 confidence를 그대로 보고한다."""
    dur_repo = _FakeDurDrugRepository([])

    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_approval_info", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)
    monkeypatch.setattr(medication_open_api_client, "fetch_dur_item_info", _empty)

    async with TestSessionLocal() as session:
        matched, auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*완전히새로운약999mg", confidence=0.99)]
        )

    assert len(matched) == 1
    drug = matched[0]
    assert drug.item_seq in auto_created_ids
    assert match_confidence[drug.item_seq] == 0.99
    # 실제 API가 담당하는 상한 적용까지 합쳐서 검증
    assert medication_service._compute_match_rate(match_confidence[drug.item_seq], is_auto_created=True) == 0.5


async def test_match_or_create_medications_no_ocr_evidence_fallback_has_no_confidence_entry():
    """(T-MED-6) OCR 텍스트가 약품명처럼 안 보여 마스터 데이터 상위 몇 개를 참고용으로만 보여주는
    경우, 그 약들은 confidence 맵에 없어야 한다 — 호출부가 기본값(낮은 match_rate)을 적용할 근거."""
    dur_repo = _FakeDurDrugRepository([("KD_NOEV001", "무근거참고약")])

    async with TestSessionLocal() as session:
        matched, _auto_created_ids, match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="환자정보", confidence=0.99)]
        )

    assert len(matched) > 0
    assert all(d.item_seq not in match_confidence for d in matched)
