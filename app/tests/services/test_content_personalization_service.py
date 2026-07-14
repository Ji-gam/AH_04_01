from app.models.disease_entries import DiagnosisEntry
from app.models.profiles import Disease, Profile
from app.services.content_personalization_service import ContentPersonalizationService


def _profile(diseases: list[Disease] | None) -> Profile:
    # [정규화] diagnosis_history(JSON list[dict]) -> diagnosis_entries(관계형 리스트, DiagnosisEntry
    # 객체). Profile(...)에 관계 필드로 바로 넘겨도 SQLAlchemy 선언적 생성자가 그대로 받아준다
    # (DB에 실제로 저장하는 게 아니라 순수 파이썬 단위테스트라 세션/커밋 필요 없음).
    entries = [DiagnosisEntry(disease=d) for d in (diseases or [])]
    return Profile(name="테스터", diagnosis_entries=entries)


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
    profile = _profile([Disease.DIABETES])

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["당뇨"]


def test_profile_with_multiple_diseases_maps_all_and_dedupes():
    profile = _profile([Disease.CANCER, Disease.DIABETES, Disease.CANCER])

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["암", "당뇨"]


def test_other_disease_maps_to_general_content_code():
    """OTHER(5대질환 외 질환)은 특정 질환 콘텐츠 대신 '기타' 일반 건강정보로 개인화된다."""
    profile = _profile([Disease.OTHER])

    personalized, diseases = ContentPersonalizationService().resolve(profile)

    assert personalized is True
    assert diseases == ["기타"]
