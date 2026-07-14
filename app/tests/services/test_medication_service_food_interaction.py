from app.services import medication_open_api_client, medication_service


async def test_food_guide_card_uses_intrc_qesitm_text(monkeypatch):
    """(T-DOC-2) e약은요 intrcQesitm 필드를 원문 그대로 GuideCard content에 담아야 한다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card("타이레놀정 500mg")

    assert card is not None
    assert card.content == "이 약을 복용하는 동안 자몽주스를 피하세요."
    assert card.severity == "caution"


async def test_food_guide_card_reports_no_interaction_when_field_empty(monkeypatch):
    """intrcQesitm이 빈 문자열이면 '확인 실패'가 아니라 '주의사항 없음'을 명시적으로 알려야 한다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": ""}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card("아스피린정 100mg")

    assert card is not None
    assert card.severity == "info"
    assert "없습니다" in card.content


async def test_food_guide_card_is_none_when_summary_empty(monkeypatch):
    """e약은요에 해당 약이 아예 없으면(빈 리스트) '없음'을 단정하지 않고 카드를 생략해야 한다."""

    async def _empty(item_name=None, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)

    card = await medication_service._build_food_interaction_guide_card("존재하지않는약")

    assert card is None


async def test_food_guide_card_is_none_when_api_errors(monkeypatch):
    """API 호출 실패는 '주의사항 없음'과 다르므로 카드를 생략(None)해야 한다 — 등록 자체는 막지 않음."""

    async def _raise(item_name=None, **kwargs):
        raise medication_open_api_client.PublicDataApiError("boom")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _raise)

    card = await medication_service._build_food_interaction_guide_card("아무거나약")

    assert card is None
