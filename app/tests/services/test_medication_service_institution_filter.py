"""약국/병원명이 OCR 텍스트에 "*" 불릿과 함께 섞여 있어도("SAMPLE*약국" 등) 약품 후보로
잡히거나 마스터 데이터에 즉석 생성되면 안 된다 — 처방전 헤더의 약국명을 실제 약으로 오인해
등록해버리는 회귀를 방지한다."""

from app.services import medication_service
from app.services.medication_service import OcrField
from app.tests.conftest import TestSessionLocal


async def test_institution_name_with_bullet_is_not_registered_as_medication():
    dur_repo = _FakeDurDrugRepository([])

    async with TestSessionLocal() as session:
        matched, auto_created_ids, _match_confidence = await medication_service._match_or_create_medications(
            session, dur_repo, [OcrField(text="*SAMPLE*약국", confidence=1.0)]
        )

    assert matched == []
    assert auto_created_ids == set()


async def test_institution_name_without_bullet_is_not_fuzzy_matched():
    """(top-3 "근거 없음" 폴백이 결과를 가릴 수 있어 `_fuzzy_match_unrecognized_fields`를
    직접 호출한다 — `_match_or_create_medications`를 거치면 "약처럼 보이는 후보가 하나도
    없을 때 마스터 데이터 상위 몇 개를 참고용으로 보여주는" 별개의 폴백 로직이 끼어들어,
    이 테스트가 확인하려는 퍼지 매칭 자체의 동작과 무관하게 결과에 후보가 섞여 든다."""
    dur_repo = _FakeDurDrugRepository([("1", "필독정")])

    async with TestSessionLocal() as session:
        matched, _confidences = await medication_service._fuzzy_match_unrecognized_fields(
            session, dur_repo, [OcrField(text="필독약국", confidence=1.0)], set()
        )

    assert matched == []


async def test_institution_name_with_trailing_particle_is_not_fuzzy_matched():
    """(#120) "본 약국의 의견과는..." 같은 실제 처방전 문구에서 조사가 붙은 "약국의"는 문자열
    끝이 "약국"으로 끝나지 않는다 — 끝 앵커만으로 걸러내면 이런 필드가 새 나가, 예전 버그로
    이미 마스터 데이터에 남아있는 쓰레기 레코드("SAMPLE*약국" 등)와 유사도 매칭돼버리는 회귀를
    방지한다. (top-3 "근거 없음" 폴백이 결과를 가릴 수 있어 `_fuzzy_match_unrecognized_fields`를
    직접 호출한다.)"""
    dur_repo = _FakeDurDrugRepository([("AUTO_TEST_STALE", "SAMPLE*약국")])

    async with TestSessionLocal() as session:
        matched, _confidences = await medication_service._fuzzy_match_unrecognized_fields(
            session, dur_repo, [OcrField(text="약국의", confidence=0.99)], set()
        )

    assert "AUTO_TEST_STALE" not in {d.item_seq for d in matched}


async def test_ingredient_mention_with_particle_does_not_fuzzy_match_unrelated_drug():
    """(#120) "아스피린에 과민증이 있는 경우..." 같은 복약안내 문구에서 "아스피린에"(성분명+조사)는
    완결된 약품명이 아닌데도, 편집거리상 실제로 등록된 다른 약("아스피린정")과 1글자 차이라
    임계값(0.8)을 넘겨 오매칭될 수 있었다. 조사로 끝나는 토큰은 퍼지 매칭에서 제외해야 한다."""
    dur_repo = _FakeDurDrugRepository([("PDP_TEST_ASPIRIN", "아스피린정")])

    async with TestSessionLocal() as session:
        matched, _confidences = await medication_service._fuzzy_match_unrecognized_fields(
            session, dur_repo, [OcrField(text="아스피린에", confidence=0.99)], set()
        )

    assert "PDP_TEST_ASPIRIN" not in {d.item_seq for d in matched}


async def test_bare_ingredient_mention_does_not_fuzzy_match_longer_unrelated_drug():
    """(#120) "아스피린 100mg"처럼 다른 약의 성분란에 적힌 성분명 단독 언급("아스피린", 조사도
    없음)이, 우연히 접미사만 다른(제형 접미사가 더 붙은) 무관한 실제 약("아스피린정")과 글자
    하나 차이로 보여(ratio≈0.89) 오매칭되던 문제. 퍼지 매칭은 "같은 길이의 글자 치환 오류"만
    구제해야 하므로, 길이가 다르면 애초에 후보에서 제외되어야 한다."""
    dur_repo = _FakeDurDrugRepository([("PDP_TEST_ASPIRIN_TABLET", "아스피린정")])

    async with TestSessionLocal() as session:
        matched, _confidences = await medication_service._fuzzy_match_unrecognized_fields(
            session, dur_repo, [OcrField(text="아스피린", confidence=0.99)], set()
        )

    assert "PDP_TEST_ASPIRIN_TABLET" not in {d.item_seq for d in matched}


class _FakeDurDrugRepository:
    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    async def search_item_names(self, session, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]

    async def search_item_names_by_prefix(self, session, prefix: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if name.startswith(prefix)][:limit]
