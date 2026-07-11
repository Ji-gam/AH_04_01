"""
T-LLM-2-dur-repository: `dur_drug_light.db`는 git에 커밋된 정적 파일이라, 실제 파일을
대상으로 조회 로직을 검증한다(별도 mock 불필요 — 값 자체가 바뀌지 않음).
"""

from app.repositories.dur_drug_repository import DurDrugRepository

repository = DurDrugRepository()


def test_find_drug_info_returns_profile_for_matching_product():
    profiles = repository.find_drug_info("활명수")

    assert len(profiles) >= 1
    assert any(p.efficacy is not None for p in profiles)


def test_find_drug_info_returns_empty_list_for_unknown_product():
    profiles = repository.find_drug_info("존재하지않는의약품이름12345")

    assert profiles == []


def test_find_dur_warnings_returns_pregnancy_warning_for_known_teratogen():
    warnings = repository.find_dur_warnings("테라싸이클린", pregnant=True, geriatric=False)

    assert any("임부금기" in w for w in warnings)


def test_find_dur_warnings_returns_empty_when_no_risk_flags():
    warnings = repository.find_dur_warnings("테라싸이클린", pregnant=False, geriatric=False)

    assert warnings == []


def test_find_dur_warnings_returns_empty_for_unknown_product():
    warnings = repository.find_dur_warnings("존재하지않는의약품이름12345", pregnant=True, geriatric=True)

    assert warnings == []
