from app.models.profiles import Profile
from app.services.content_personalization_service import ContentPersonalizationService


def _profile(diagnosis_history: list[dict] | None) -> Profile:
    return Profile(name="테스터", diagnosis_history=diagnosis_history)


def test_anonymous_profile_is_not_personalized():
    personalized, diseases = ContentPersonalizationService().resolve(None)

    assert personalized is False
    assert diseases is None


def test_profile_without_diagnosis_history_is_not_personalized():
    personalized, diseases = ContentPersonalizationService().resolve(_profile(None))

    assert personalized is False
    assert diseases is None


def test_profile_with_empty_diagnosis_history_is_not_personalized():
    personalized, diseases = ContentPersonalizationService().resolve(_profile([]))

    assert personalized is False
    assert diseases is None


def test_profile_with_registered_disease_maps_to_korean_disease_code():
    profile = _profile([{"disease": "DIABETES", "detail": None}])

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["당뇨"]


def test_profile_with_multiple_diseases_maps_all_and_dedupes():
    profile = _profile(
        [
            {"disease": "CANCER", "detail": None},
            {"disease": "DIABETES", "detail": "10년째 투병 중"},
            {"disease": "CANCER", "detail": "중복 등록"},
        ]
    )

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["암", "당뇨"]


def test_other_disease_maps_to_general_content_code():
    """OTHER(5대질환 외 질환)은 특정 질환 콘텐츠 대신 '기타' 일반 건강정보로 개인화된다."""
    profile = _profile([{"disease": "OTHER", "detail": "루푸스"}])

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["기타"]
