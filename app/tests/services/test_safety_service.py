import pytest

from app.services import safety_service


@pytest.mark.parametrize(
    "message",
    [
        "가슴 통증이 있어요",  # 기존(공백 포함)
        "가슴통증",  # 공백 없는 변형
        "가슴이 아파요",  # 표현 변형
        "가슴이 조여와요",
        "숨이 안 쉬어져요",  # 기존
        "숨쉬기 힘들어요",  # 표현 변형
        "호흡곤란이 와요",
        "의식이 없어요",  # 기존
        "갑자기 쓰러졌어요",
        "죽고 싶어요",  # 자살 위험 — fallback 1393 안내 대상
    ],
)
def test_check_emergency_detects_variants(message):
    assert safety_service.check_emergency(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "약 복용 시간을 알려주세요",
        "혈압약을 언제 먹어야 하나요",
        "오늘 날씨가 좋네요",
    ],
)
def test_check_emergency_ignores_non_emergency(message):
    assert safety_service.check_emergency(message) is False


@pytest.mark.parametrize(
    "message,response",
    [
        ("콘서타 먹어도 되나요?", "임산부는 복용 시 주의해야 합니다."),
        ("감기약 처방전 질문", "이 약물은 부작용이..."),
        ("당뇨 관리 어떻게", "혈당 관리가 중요합니다."),
    ],
)
def test_is_medical_related_detects_medical_conversation(message, response):
    assert safety_service.is_medical_related(message, response) is True


@pytest.mark.parametrize(
    "message,response",
    [
        ("오늘 날씨 어때?", "오늘 날씨는 매우 맑고 따뜻할 예정입니다."),
        ("초코칩 쿠키 레시피 알려줘", "밀가루와 설탕을 섞어 구우면 됩니다."),
    ],
)
def test_is_medical_related_ignores_non_medical(message, response):
    assert safety_service.is_medical_related(message, response) is False


def test_apply_disclaimer_appends_disclaimer_text():
    reply = "복약 시간을 놓치셨다면 다음 복용 시간에 정량만 드세요."

    result = safety_service.apply_disclaimer(reply)

    assert reply in result
    assert safety_service.DISCLAIMER_TEXT in result


def test_apply_disclaimer_present_even_for_empty_reply():
    result = safety_service.apply_disclaimer("")

    assert safety_service.DISCLAIMER_TEXT in result
