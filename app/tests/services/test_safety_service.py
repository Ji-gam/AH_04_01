from app.services import safety_service


def test_apply_disclaimer_appends_disclaimer_text():
    reply = "복약 시간을 놓치셨다면 다음 복용 시간에 정량만 드세요."

    result = safety_service.apply_disclaimer(reply)

    assert reply in result
    assert safety_service.DISCLAIMER_TEXT in result


def test_apply_disclaimer_present_even_for_empty_reply():
    result = safety_service.apply_disclaimer("")

    assert safety_service.DISCLAIMER_TEXT in result
