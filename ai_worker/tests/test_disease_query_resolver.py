"""질환 사전(disease_query_resolver)의 판별/확장 규칙 검증.
가장 위험한 건 오탐이다 — "암"/"간"은 한국어에서 흔한 음절이라("암기", "시간", "간단")
부분 문자열 매칭이 엉뚱한 질문을 질환 질문으로 오인할 수 있다."""

from ai_worker.services.disease_query_resolver import resolve_diseases


def test_resolve_maps_direct_disease_keywords():
    assert resolve_diseases("당뇨병 환자 식단 관리") == ["당뇨"]
    assert resolve_diseases("혈당이 높으면 어떡하죠?") == ["당뇨"]
    assert resolve_diseases("협심증 진단받았어요") == ["심장질환"]
    assert resolve_diseases("뇌졸중 재활 운동") == ["뇌혈관질환"]
    assert resolve_diseases("지방간에 좋은 음식") == ["간질환"]
    assert resolve_diseases("항암치료 중 식사") == ["암"]


def test_resolve_maps_hypertension_to_cardio_and_cerebro():
    """고혈압은 5대 질환에 없지만 심혈관/뇌혈관 논문이 실제 답이 된다."""
    assert resolve_diseases("고혈압에 좋은 운동은?") == ["심장질환", "뇌혈관질환"]


def test_resolve_returns_multiple_diseases_for_compound_question():
    result = resolve_diseases("당뇨랑 심장질환 둘 다 있는데 운동해도 되나요?")

    assert set(result) == {"당뇨", "심장질환"}


def test_resolve_does_not_false_positive_on_common_syllables():
    """'암'/'간'이 들어간 일상어를 질환 질문으로 오인하면 안 된다."""
    assert resolve_diseases("이거 암기해야 하나요?") == []
    assert resolve_diseases("시간이 얼마나 걸려요?") == []
    assert resolve_diseases("간단하게 알려주세요") == []
    assert resolve_diseases("인간관계가 힘들어요") == []


def test_resolve_falls_back_to_user_conditions():
    assert resolve_diseases("운동 뭐가 좋아?", ["당뇨"]) == ["당뇨"]


def test_resolve_prefers_query_over_user_conditions():
    """질의에 질환이 명시되면 본인 진단 이력보다 질의를 따른다 —
    당뇨 환자도 가족의 암에 대해 물을 수 있다."""
    assert resolve_diseases("항암치료 부작용이 궁금해요", ["당뇨"]) == ["암"]


def test_resolve_drops_conditions_without_papers():
    """'기타'처럼 논문이 없는 진단 코드는 필터에 쓰면 안 된다(결과 0건 확정)."""
    assert resolve_diseases("운동 뭐가 좋아?", ["기타"]) == []


def test_resolve_returns_empty_when_nothing_matches():
    assert resolve_diseases("좋은 아침이야") == []
    assert resolve_diseases("고마워요", []) == []


def test_resolve_returns_empty_when_nothing_matches_and_no_conditions():
    assert resolve_diseases("팔단금 운동이 균형에 도움이 되나요?") == []
