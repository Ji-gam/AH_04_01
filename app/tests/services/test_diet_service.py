from dataclasses import dataclass
from datetime import date
from typing import cast

from app.models.profiles import Gender
from app.services.diet_service import (
    DietKcalReasonSummary,
    _compute_reference_kcal,
    _fallback_kcal_reason,
)


@dataclass
class FakeHealthProfile:
    height_cm: float | None
    weight_kg: float | None
    gender: Gender | None
    birth_date: date | None


def test_compute_reference_kcal_personalizes_for_male_with_full_info():
    """Mifflin-St Jeor 공식: BMR = 10*w + 6.25*h - 5*age + 5, 활동계수 1.375, 50kcal 단위 반올림."""
    health = FakeHealthProfile(height_cm=175, weight_kg=70, gender=Gender.MALE, birth_date=date(1996, 7, 30))

    reference_kcal, personalized = _compute_reference_kcal(cast(object, health))

    assert personalized is True
    bmr = 10 * 70 + 6.25 * 175 - 5 * 30 + 5
    expected = round(bmr * 1.375 / 50) * 50
    assert reference_kcal == expected


def test_compute_reference_kcal_personalizes_for_female():
    health = FakeHealthProfile(height_cm=160, weight_kg=55, gender=Gender.FEMALE, birth_date=date(1996, 7, 30))

    reference_kcal, personalized = _compute_reference_kcal(cast(object, health))

    assert personalized is True
    bmr = 10 * 55 + 6.25 * 160 - 5 * 30 - 161
    expected = round(bmr * 1.375 / 50) * 50
    assert reference_kcal == expected


def test_compute_reference_kcal_falls_back_when_health_profile_is_none():
    reference_kcal, personalized = _compute_reference_kcal(None)
    assert reference_kcal == 2000
    assert personalized is False


def test_compute_reference_kcal_falls_back_when_height_missing():
    health = FakeHealthProfile(height_cm=None, weight_kg=55, gender=Gender.FEMALE, birth_date=date(1996, 7, 30))
    reference_kcal, personalized = _compute_reference_kcal(cast(object, health))
    assert reference_kcal == 2000
    assert personalized is False


def test_compute_reference_kcal_falls_back_when_gender_missing():
    health = FakeHealthProfile(height_cm=160, weight_kg=55, gender=None, birth_date=date(1996, 7, 30))
    reference_kcal, personalized = _compute_reference_kcal(cast(object, health))
    assert reference_kcal == 2000
    assert personalized is False


def test_compute_reference_kcal_falls_back_when_birth_date_missing():
    health = FakeHealthProfile(height_cm=160, weight_kg=55, gender=Gender.FEMALE, birth_date=None)
    reference_kcal, personalized = _compute_reference_kcal(cast(object, health))
    assert reference_kcal == 2000
    assert personalized is False


def test_fallback_kcal_reason_mentions_generic_when_not_personalized():
    reason = _fallback_kcal_reason(False, 2000, None)
    assert "2000kcal" in reason
    assert "일반 성인" in reason


def test_fallback_kcal_reason_mentions_height_weight_when_personalized():
    health = FakeHealthProfile(height_cm=170, weight_kg=65, gender=Gender.FEMALE, birth_date=date(1996, 7, 30))
    reason = _fallback_kcal_reason(True, 1750, cast(object, health))
    assert "170" in reason
    assert "65" in reason


def test_diet_kcal_reason_summary_schema_has_reason_field():
    summary = DietKcalReasonSummary(reason="테스트 이유")
    assert summary.reason == "테스트 이유"
