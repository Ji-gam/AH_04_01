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


async def test_food_guide_card_reports_unavailable_when_summary_empty(monkeypatch):
    """e약은요에 해당 약이 아예 없으면(빈 리스트) '주의사항 없음'을 단정하지 않고, '확인 불가'를
    명시하는 카드를 반환해야 한다 — 등록약 여러 개 중 일부만 카드가 사라지면 그 약은 검사
    안 한 것처럼 보이므로, 카드 자체는 항상 반환한다."""

    async def _empty(item_name=None, **kwargs):
        return []

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _empty)

    card = await medication_service._build_food_interaction_guide_card("존재하지않는약")

    assert card is not None
    assert card.severity == "info"
    assert "찾지 못해" in card.content


async def test_food_guide_card_filters_out_drug_only_interaction_text(monkeypatch):
    """intrcQesitm은 "약 또는 음식" 둘 다 섞여 있어, 다른 약과의 병용 얘기만 있고 음식/음주
    언급이 없으면(실 API로 확인된 실제 케이스) '주의사항 없음'으로 처리해야 한다 — 약물 간
    상호작용 텍스트를 음식 탭에 그대로 보여주면 오해를 준다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [
            {
                "itemName": item_name,
                "intrcQesitm": (
                    "메토트렉세이트 15밀리그람 이상의 용량과 함께 사용하지 마십시오. "
                    "항응고제, 혈전용해제, 이부프로펜을 복용하는 환자는 의사 또는 약사와 상의하십시오."
                ),
            }
        ]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card("어떤약")

    assert card is not None
    assert card.severity == "info"
    assert "없습니다" in card.content


async def test_food_guide_card_keeps_only_food_related_sentence_among_mixed_text(monkeypatch):
    """약물 상호작용 문장과 음식 관련 문장이 섞여 있으면 음식 문장만 남겨야 한다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [
            {
                "itemName": item_name,
                "intrcQesitm": ("와파린과 함께 사용하지 마십시오. 알코올과 병용 시 위장관 출혈 위험이 증가합니다."),
            }
        ]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card("어떤약")

    assert card is not None
    assert card.severity == "caution"
    assert "알코올" in card.content
    assert "와파린" not in card.content


async def test_food_guide_card_retries_with_dosage_suffix_stripped(monkeypatch):
    """e약은요 itemName은 정확/부분 일치라 'NNmg' 접미사가 실제 품목명과 안 맞으면 빈 결과가
    흔하다(실 API로 확인: "아스피린정 100mg" 0건, "아스피린정" 1건) — 접미사를 뗀 이름으로
    재시도해야 한다."""

    async def _fake_summary(item_name=None, **kwargs):
        if item_name == "아스피린정 100mg":
            return []
        assert item_name == "아스피린정"
        return [{"itemName": item_name, "intrcQesitm": "알코올과 함께 복용하지 마세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card("아스피린정 100mg")

    assert card is not None
    assert card.content == "알코올과 함께 복용하지 마세요."


async def test_food_guide_card_reports_unavailable_when_api_errors(monkeypatch):
    """API 호출 실패는 '주의사항 없음'과 다르므로 '확인 불가' 카드를 반환해야 한다(등록 자체는
    막지 않음, 카드 자체는 생략하지 않음)."""

    async def _raise(item_name=None, **kwargs):
        raise medication_open_api_client.PublicDataApiError("boom")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _raise)

    card = await medication_service._build_food_interaction_guide_card("아무거나약")

    assert card is not None
    assert card.severity == "info"
    assert "찾지 못해" in card.content
