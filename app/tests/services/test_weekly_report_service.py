from dataclasses import dataclass
from decimal import Decimal

from app.services.weekly_report_service import _body_info_line


@dataclass
class FakeHealthProfile:
    height_cm: Decimal | None
    weight_kg: Decimal | None


@dataclass
class FakeProfile:
    health_profile: FakeHealthProfile | None


def test_body_info_line_includes_bmi_when_both_height_and_weight_present():
    """주간 리포트에 키/몸무게를 반영해달라는 요청 - 둘 다 있으면 BMI까지 계산해 한 줄로 만든다."""
    profile = FakeProfile(health_profile=FakeHealthProfile(height_cm=Decimal("170"), weight_kg=Decimal("65")))

    line = _body_info_line(profile)  # type: ignore[arg-type]

    assert line == "키 170cm, 몸무게 65kg (BMI 22.5)"


def test_body_info_line_is_none_when_height_missing():
    profile = FakeProfile(health_profile=FakeHealthProfile(height_cm=None, weight_kg=Decimal("65")))
    assert _body_info_line(profile) is None  # type: ignore[arg-type]


def test_body_info_line_is_none_when_weight_missing():
    profile = FakeProfile(health_profile=FakeHealthProfile(height_cm=Decimal("170"), weight_kg=None))
    assert _body_info_line(profile) is None  # type: ignore[arg-type]


def test_body_info_line_is_none_when_health_profile_missing():
    profile = FakeProfile(health_profile=None)
    assert _body_info_line(profile) is None  # type: ignore[arg-type]


def test_body_info_line_is_none_when_profile_is_none():
    assert _body_info_line(None) is None
