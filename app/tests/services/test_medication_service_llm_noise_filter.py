from app.services import medication_service
from app.tests.conftest import TestSessionLocal


class _FakeDurDrugRepository:
    """실제 마스터 DB 대신, 테스트가 통제하는 (item_seq, item_name) 목록만 돌려준다."""

    def __init__(self, items: list[tuple[str, str]]):
        self._items = items

    async def search_item_names(self, session, item_name: str, limit: int) -> list[tuple[str, str]]:
        return [(seq, name) for seq, name in self._items if item_name in name][:limit]


def test_is_plausible_llm_drug_name_rejects_receipt_caption_and_numeric_code():
    """(#OCR-LLM) LLM이 프롬프트 지시를 무시하고 영수증 문구/숫자 코드를 약품명으로 제안해도
    걸러야 한다 - 실제 사용자가 겪은 "전액본인부담금이란", "201501025" 오등록 사례."""
    assert medication_service._is_plausible_llm_drug_name("전액본인부담금이란") is False
    assert medication_service._is_plausible_llm_drug_name("201501025") is False


def test_is_plausible_llm_drug_name_accepts_real_drug_shapes():
    assert medication_service._is_plausible_llm_drug_name("리피로우정20mg") is True
    assert medication_service._is_plausible_llm_drug_name("노스판패취10ug/h") is True
    assert medication_service._is_plausible_llm_drug_name("글루코파지엑스알100mg서방정") is True


def test_is_plausible_llm_drug_name_rejects_bare_ingredient_salt_with_dosage():
    """(#OCR-LLM-3) 제형 접미사 없이 성분명(염산염/말레산염 등)+용량만 있는 줄은, 처방전에서
    브랜드명 카드 아래 붙는 설명 줄이지 별도 약이 아니다 - 실제 사용자가 겪은
    "클로르페니라민말레산염2mg", "슈도에페드린연산염60mg" 오등록 사례."""
    assert medication_service._is_plausible_llm_drug_name("클로르페니라민말레산염2mg") is False
    assert medication_service._is_plausible_llm_drug_name("슈도에페드린연산염60mg") is False


def test_looks_like_drug_name_rejects_bulleted_receipt_caption():
    """(#OCR-LLM-2) "*" 불릿 조건은 제형 접미사 검사를 건너뛰므로, "*전액본인부담금이란"처럼
    영수증 설명 문구가 "*"와 함께 오인식되면 필터 없이 통과해 매 스캔마다 새 AUTO_ 더미로
    재등록됐다 - 조사/설명 어미로 끝나면 "*"가 붙어 있어도 걸러야 한다."""
    assert medication_service._looks_like_drug_name("*전액본인부담금이란") is False
    assert medication_service._looks_like_drug_name("전액본인부담금이란") is False


def test_looks_like_drug_name_still_accepts_bulleted_brand_names():
    assert medication_service._looks_like_drug_name("*리피로우정20mg") is True
    assert medication_service._looks_like_drug_name("*노스판패취10ug/h") is True


def test_is_duplicate_of_seen_name_catches_ocr_typo_vs_llm_correction():
    """마스터 DB에 없는 약은 정규식 경로가 OCR 원문 오탈자("노스판매취10ug/h")로, LLM 경로가
    교정 표기("노스판패취10ug/h")로 각각 후보를 만들면 문자열이 달라 완전일치로는 안 걸리고
    각자 별도 item_seq를 받아 같은 약이 2번 등록됐다. 한글 편집거리로 같은 약임을 인식해야 한다."""
    seen = {"노스판매취10ug/h"}
    assert medication_service._is_duplicate_of_seen_name("노스판패취10ug/h", seen) is True


def test_is_duplicate_of_seen_name_allows_distinct_drugs():
    """서로 다른 약은 억제하지 않는다 — 한 처방전에 함께 있어도 각각 등록돼야 한다."""
    seen = {"리피로우정20mg"}
    assert medication_service._is_duplicate_of_seen_name("아스피린정100mg", seen) is False
    assert medication_service._is_duplicate_of_seen_name("리피로우정20mg", seen) is True


async def test_resolve_llm_suggested_names_filters_out_noise_before_registering():
    """(#OCR-LLM) `_resolve_llm_suggested_names`가 노이즈 이름을 마스터 DB/AUTO_ 더미 생성
    단계까지 보내지 않고 그 전에 걸러야 한다."""
    dur_repo = _FakeDurDrugRepository([])

    async with TestSessionLocal() as session:
        resolved, auto_created_ids = await medication_service._resolve_llm_suggested_names(
            session,
            dur_repo,
            ["전액본인부담금이란", "201501025", "리피로우정20mg"],
            set(),
            set(),
        )

    resolved_names = {drug.item_name for drug in resolved}
    assert resolved_names == {"리피로우정20mg"}
    assert len(auto_created_ids) == 1
