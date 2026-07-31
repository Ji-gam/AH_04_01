from app.repositories.dur_drug_repository import DurDrugRepository
from app.services import medication_open_api_client, medication_service
from app.tests.conftest import TestSessionLocal


def _no_local_snapshot_match(monkeypatch):
    """(T-DOC-5) `drugs_data`(MySQL 2단계 스냅샷)에 이 약이 없다고 가정해, 느린 3단계(e약은요
    실시간 API)까지 반드시 도달하게 만든다. 실제 시딩된 운영 데이터(`seed_dur`)와 무관하게
    결정적으로 동작하도록 리포지토리 메서드 자체를 고정한다."""

    async def _fake_find(self, session, item_name):
        return None

    monkeypatch.setattr(DurDrugRepository, "find_food_intrc_text", _fake_find)


async def test_food_guide_card_uses_intrc_qesitm_text(monkeypatch):
    """(T-DOC-2) e약은요 intrcQesitm 필드를 원문 그대로 GuideCard content에 담아야 한다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card_slow("타이레놀정 500mg")

    assert card is not None
    assert card.content == "이 약을 복용하는 동안 자몽주스를 피하세요."
    assert card.severity == "caution"


async def test_food_guide_card_reports_no_interaction_when_field_empty(monkeypatch):
    """intrcQesitm이 빈 문자열이면 '확인 실패'가 아니라 '주의사항 없음'을 명시적으로 알려야 한다.
    (T-DOC-3) "아스피린"은 참조 테이블에 매칭되는 성분명이라 다른 이름을 쓴다 — 이 테스트는
    e약은요 폴백 경로의 빈 필드 처리만 검증하려는 목적."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": ""}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card_slow("다이아벡스정 500mg")

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

    card = await medication_service._build_food_interaction_guide_card_slow("존재하지않는약")

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

    card = await medication_service._build_food_interaction_guide_card_slow("어떤약")

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

    card = await medication_service._build_food_interaction_guide_card_slow("어떤약")

    assert card is not None
    assert card.severity == "caution"
    assert "알코올" in card.content
    assert "와파린" not in card.content


async def test_food_guide_card_retries_with_dosage_suffix_stripped(monkeypatch):
    """e약은요 itemName은 정확/부분 일치라 'NNmg' 접미사가 실제 품목명과 안 맞으면 빈 결과가
    흔하다(실 API로 확인: "아스피린정 100mg" 0건, "아스피린정" 1건) — 접미사를 뗀 이름으로
    재시도해야 한다. (T-DOC-3) "아스피린"은 참조 테이블에 매칭되는 성분명이라 이 테스트는
    다른 이름을 쓴다 — 검증 대상은 접미사 제거 재시도 로직뿐."""

    async def _fake_summary(item_name=None, **kwargs):
        if item_name == "다이아벡스정 500mg":
            return []
        assert item_name == "다이아벡스정"
        return [{"itemName": item_name, "intrcQesitm": "알코올과 함께 복용하지 마세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card_slow("다이아벡스정 500mg")

    assert card is not None
    assert card.content == "알코올과 함께 복용하지 마세요."


async def test_food_guide_card_uses_mfds_reference_when_ingredient_name_matches(monkeypatch):
    """(T-DOC-3) 품목명에 참조 테이블(식약처 「약과 음식 상호작용을 피하는 복약안내서」) 성분명이
    포함되면 그 원문을 우선 사용하고, MySQL 스냅샷/e약은요 API는 호출하지 않는다 — 국내
    일반의약품은 품목명에 성분명이 그대로 들어가는 경우가 흔하다(예: "와파린정5mg")."""

    async def _fail_if_called(item_name=None, **kwargs):
        raise AssertionError("참조 테이블에 매칭되면 e약은요를 호출하지 않아야 한다")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fail_if_called)

    async with TestSessionLocal() as session:
        card = await medication_service._build_food_interaction_guide_card_fast(session, "와파린정5mg")

    assert card is not None
    assert card.severity == "caution"
    assert "비타민 K" in card.content
    assert "복약안내서" in card.content


async def test_food_guide_card_falls_back_to_intrc_qesitm_when_no_reference_match(monkeypatch):
    """(T-DOC-3/T-DOC-5) 참조 테이블에도, MySQL `drugs_data` 스냅샷에도 매칭되는 성분/품목이
    없으면(상표명이면서 스냅샷 밖) 느린 3단계 e약은요 API로 그대로 폴백한다 — T-DOC-2 동작
    회귀 확인."""
    _no_local_snapshot_match(monkeypatch)

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    async with TestSessionLocal() as session:
        fast_card = await medication_service._build_food_interaction_guide_card_fast(session, "타이레놀정 500mg")
        assert fast_card is None
        card = await medication_service._build_food_interaction_guide_card(session, "타이레놀정 500mg")

    assert card is not None
    assert card.content == "이 약을 복용하는 동안 자몽주스를 피하세요."
    assert card.severity == "caution"


async def test_food_guide_card_uses_local_snapshot_without_calling_live_api(monkeypatch):
    """(T-DOC-5) 참조 테이블에는 없지만 MySQL `drugs_data` 스냅샷(2단계)에 있으면, 실시간
    e약은요 API(3단계)는 호출하지 않고 스냅샷 텍스트로 카드를 만들어야 한다."""

    async def _fake_find(self, session, item_name):
        return "이 약을 복용하는 동안 자몽주스를 피하세요."

    monkeypatch.setattr(DurDrugRepository, "find_food_intrc_text", _fake_find)

    async def _fail_if_called(item_name=None, **kwargs):
        raise AssertionError("MySQL 스냅샷에 매칭되면 실시간 e약은요 API를 호출하지 않아야 한다")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fail_if_called)

    async with TestSessionLocal() as session:
        card = await medication_service._build_food_interaction_guide_card_fast(session, "타이레놀정 500mg")

    assert card is not None
    assert card.content == "이 약을 복용하는 동안 자몽주스를 피하세요."
    assert card.severity == "caution"


async def test_food_guide_card_reports_unavailable_when_api_errors(monkeypatch):
    """API 호출 실패는 '주의사항 없음'과 다르므로 '확인 불가' 카드를 반환해야 한다(등록 자체는
    막지 않음, 카드 자체는 생략하지 않음)."""

    async def _raise(item_name=None, **kwargs):
        raise medication_open_api_client.PublicDataApiError("boom")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _raise)

    card = await medication_service._build_food_interaction_guide_card_slow("아무거나약")

    assert card is not None
    assert card.severity == "info"
    assert "찾지 못해" in card.content


def test_extract_food_items_groups_by_known_name_and_avoids_substring_duplicates():
    """(T-DOC-4) 사전에 있는 음식/음료 명사가 등장한 문장을 묶되, 더 구체적인 이름(예: "자몽주스")이
    매칭되면 그 안에 포함된 짧은 이름(예: "자몽")은 중복이므로 제외해야 한다."""
    text = "자몽주스와 자몽은 모두 피하세요. 비타민 K가 많은 시금치를 조심하세요."

    items = medication_service._extract_food_items(text)

    names = {item.name for item in items}
    assert "자몽주스" in names
    assert "자몽" not in names
    assert "비타민 K" in names
    assert "시금치" in names


async def test_food_guide_card_populates_food_items_from_mfds_reference(monkeypatch):
    """(T-DOC-4) 참조 테이블 매칭 카드는 사전에 있는 음식/음료 명사를 food_items로도 채워야
    한다 — 프론트가 이유 줄글 대신 음식명 칩을 먼저 보여줄 수 있게 하기 위함."""

    async def _fail_if_called(item_name=None, **kwargs):
        raise AssertionError("참조 테이블에 매칭되면 e약은요를 호출하지 않아야 한다")

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fail_if_called)

    async with TestSessionLocal() as session:
        card = await medication_service._build_food_interaction_guide_card_fast(session, "와파린정5mg")

    assert card is not None
    assert card.food_items is not None
    names = {item.name for item in card.food_items}
    assert "비타민 K" in names
    for item in card.food_items:
        assert item.detail


async def test_food_guide_card_populates_food_items_from_intrc_qesitm_when_known_food_mentioned(monkeypatch):
    """(T-DOC-4) e약은요 폴백 경로에서도 사전에 있는 음식이 언급되면 food_items를 채운다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약을 복용하는 동안 자몽주스를 피하세요."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card_slow("타이레놀정 500mg")

    assert card.food_items is not None
    assert card.food_items[0].name == "자몽주스"
    assert "자몽주스" in card.food_items[0].detail


async def test_food_guide_card_leaves_food_items_none_when_no_known_food_mentioned(monkeypatch):
    """(T-DOC-4) 사전에 없는 음식/음료만 언급되면 food_items는 None으로 두고, 프론트가 기존처럼
    content 전체를 보여주도록 폴백한다."""

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemName": item_name, "intrcQesitm": "이 약은 낫토와 청국장 섭취 시 주의가 필요합니다."}]

    monkeypatch.setattr(medication_open_api_client, "fetch_drug_summary", _fake_summary)

    card = await medication_service._build_food_interaction_guide_card_slow("다이아벡스정 500mg")

    assert card.food_items is None
    assert "낫토" in card.content
