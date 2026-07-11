from dataclasses import dataclass, field

from app.services.chat_context_service import ChatContextService


@dataclass
class FakeProfile:
    id: int
    name: str = "사용자"
    age: int | None = None
    diagnosis_history: list[dict] | None = None
    family_history: list[dict] | None = None


@dataclass
class FakeMedication:
    medication_name: str


@dataclass
class FakeMedicationSchedule:
    medication: FakeMedication
    times: list[str] = field(default_factory=lambda: ["08:00"])


def test_none_profile_returns_anonymous_context():
    context = ChatContextService().build(None, [])

    assert context["name"] == "사용자"
    assert context["conditions"] == []
    assert context["is_pregnant"] is False
    assert context["is_geriatric"] is False


def test_diagnosis_history_maps_to_korean_disease_codes():
    profile = FakeProfile(id=1, diagnosis_history=[{"disease": "DIABETES", "detail": None}])

    context = ChatContextService().build(profile, [])

    assert context["conditions"] == ["당뇨"]


def test_age_over_threshold_is_geriatric():
    profile = FakeProfile(id=1, age=70)

    context = ChatContextService().build(profile, [])

    assert context["is_geriatric"] is True


def test_age_under_threshold_is_not_geriatric():
    profile = FakeProfile(id=1, age=40)

    context = ChatContextService().build(profile, [])

    assert context["is_geriatric"] is False


def test_is_pregnant_is_always_false_no_real_data_source():
    """Profile 스키마에 임신 여부 필드가 없어 항상 False다(#71에서 스키마 추가 요청 중)."""
    profile = FakeProfile(id=1)

    context = ChatContextService().build(profile, [])

    assert context["is_pregnant"] is False


def test_medications_maps_name_and_times_per_day():
    profile = FakeProfile(id=1)
    medications = [FakeMedicationSchedule(medication=FakeMedication("메트포르민"), times=["08:00", "20:00"])]

    context = ChatContextService().build(profile, medications)

    assert context["medications"] == [{"name": "메트포르민", "times_per_day": 2}]
