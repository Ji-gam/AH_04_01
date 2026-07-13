"""T-MED-13: extracted_fields(dosage/times/duration/instruction)가 더 이상
CLOVA 인식 결과와 무관하게 하드코딩된 값으로 고정되지 않는지 검증한다."""

from app.services import medication_service


def test_parse_dosage_fields_extracts_real_values_from_ocr_text():
    raw_text = "*타이레놀정 1회 2정 1일 3회 3일분 식후 30분 복용 09:00 13:00 19:00"

    result = medication_service._parse_dosage_fields(raw_text)

    assert result == {
        "dosage": "2정",
        "times": ["09:00", "13:00", "19:00"],
        "duration": "3일",
        "instruction": "식후 30분",
    }


def test_parse_dosage_fields_returns_none_when_pattern_not_found():
    raw_text = "*알수없는텍스트 약국 안내문구"

    result = medication_service._parse_dosage_fields(raw_text)

    assert result == {"dosage": None, "times": None, "duration": None, "instruction": None}


def test_parse_dosage_fields_is_partial_not_all_or_nothing():
    """일부 필드만 OCR 텍스트에서 발견되면, 발견된 것만 채우고 나머지는 None이어야 한다
    (과거처럼 하나라도 못 찾으면 나머지까지 고정 더미로 채우지 않는다)."""
    raw_text = "*아스피린정 1회 1정"

    result = medication_service._parse_dosage_fields(raw_text)

    assert result["dosage"] == "1정"
    assert result["times"] is None
    assert result["duration"] is None
    assert result["instruction"] is None


def test_dummy_dosage_fields_keeps_fixed_illustrative_values():
    """dummy_mode 경로는 confidence(T-MED-6)와 마찬가지로 결정적 테스트 데이터라 예시값을
    유지한다 — dummy_mode=True 플래그로 이미 실인식과 명시적으로 구분되므로 문제 없다."""
    result = medication_service._dummy_dosage_fields()

    assert result == {
        "dosage": "1정",
        "times": ["09:00", "13:00", "19:00"],
        "duration": "3일",
        "instruction": "식후 30분 복용",
    }
