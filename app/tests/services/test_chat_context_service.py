from dataclasses import dataclass, field

from app.models.profiles import Disease
from app.services.chat_context_service import ChatContextService


@dataclass
class FakeDiagnosisEntry:
    """`chat_context_service.py`가 `e.disease.value`로 읽으므로, disease는 실제 Disease enum을 쓴다."""

    disease: Disease


@dataclass
class FakeHealthProfile:
    """[2026-07-29 PII/건강정보 분리] is_pregnant는 이제 profile.health_profile 경유로
    읽힌다 - 실제 HealthProfile 모델과 같은 인터페이스(속성명)를 흉내낸 테스트 더블."""

    is_pregnant: bool | None = None


@dataclass
class FakeProfile:
    # [정규화] diagnosis_history(JSON) -> diagnosis_entries(관계형 리스트)로 필드명/타입 변경.
    id: int
    name: str = "사용자"
    age: int | None = None
    health_profile: FakeHealthProfile | None = None
    diagnosis_entries: list[FakeDiagnosisEntry] = field(default_factory=list)
    family_history_entries: list[FakeDiagnosisEntry] = field(default_factory=list)


@dataclass
class FakeMedicationSchedule:
    item_seq: str
    display_name: str | None = None
    times: list[str] = field(default_factory=lambda: ["08:00"])


def test_none_profile_returns_anonymous_context():
    context = ChatContextService().build(None, [])

    assert context["name"] == "사용자"
    assert context["conditions"] == []
    assert context["is_pregnant"] is False
    assert context["is_geriatric"] is False


def test_diagnosis_history_maps_to_korean_disease_codes():
    profile = FakeProfile(id=1, diagnosis_entries=[FakeDiagnosisEntry(disease=Disease.DIABETES)])

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


def test_is_pregnant_true_reads_from_profile():
    """[#71 해결] 이제 HealthProfile.is_pregnant를 개인건강정보에서 실제로 입력받아 그대로 읽는다."""
    profile = FakeProfile(id=1, health_profile=FakeHealthProfile(is_pregnant=True))

    context = ChatContextService().build(profile, [])

    assert context["is_pregnant"] is True


def test_is_pregnant_false_reads_from_profile():
    profile = FakeProfile(id=1, health_profile=FakeHealthProfile(is_pregnant=False))

    context = ChatContextService().build(profile, [])

    assert context["is_pregnant"] is False


def test_is_pregnant_defaults_to_false_when_unanswered():
    """미입력(None)이면 임부금기 경고 게이팅 목적상 False로 취급한다(모른다 != 아니다이지만,
    현재는 안전하게 "경고 비활성"으로 처리)."""
    profile = FakeProfile(id=1, health_profile=FakeHealthProfile(is_pregnant=None))

    context = ChatContextService().build(profile, [])

    assert context["is_pregnant"] is False


def test_medications_maps_name_and_times_per_day():
    profile = FakeProfile(id=1)
    medications = [FakeMedicationSchedule(item_seq="111", display_name="메트포르민", times=["08:00", "20:00"])]

    context = ChatContextService().build(profile, medications)

    assert context["medications"] == [{"name": "메트포르민", "times_per_day": 2}]


def test_medications_falls_back_to_resolved_drug_names_when_no_display_name():
    """(T-MED-16) 마스터 데이터에서 찾은 약은 display_name이 비어 있으므로, 호출자가 미리
    조회해 넘긴 `drug_names`에서 이름을 가져와야 한다."""
    profile = FakeProfile(id=1)
    medications = [FakeMedicationSchedule(item_seq="111", times=["08:00"])]

    context = ChatContextService().build(profile, medications, {"111": "메트포르민"})

    assert context["medications"] == [{"name": "메트포르민", "times_per_day": 1}]
