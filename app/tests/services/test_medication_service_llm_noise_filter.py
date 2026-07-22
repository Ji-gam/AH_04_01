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
