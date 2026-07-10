"""
공통모듈 — 질병/복약/목표 조회 단일창구(`docs/decision_log.md` "공통 모듈" 표).
생체정보/복약정보 도메인 테이블·ERD·T-ID가 아직 없어(PM 확인 대기 중) Tier 2
stub으로 채운다(`docs/CODING_RULES.md` 8번). 아래 값은 profile_id별로 다른 하드코딩
목업이며 실제 사용자 데이터가 아니다 — 병력이 LLM 프롬프트에 반영되는 흐름만
검증하기 위한 프로토타입 용도. 해당 도메인 테이블이 확정되면 이 클래스 내부만
실제 조회 로직으로 교체한다.
"""

_MOCK_HEALTH_PROFILES: dict[int, dict] = {
    1: {
        "conditions": ["당뇨"],
        "family_history": ["암", "심장질환"],
        "medications": [
            {"condition": "당뇨", "name": "메트포르민", "dose": "500mg", "times_per_day": 2},
        ],
    },
    2: {
        "conditions": ["고혈압", "간질환"],
        "family_history": ["뇌혈관질환"],
        "medications": [
            {"condition": "고혈압", "name": "암로디핀", "dose": "5mg", "times_per_day": 1},
        ],
    },
    4: {
        "conditions": ["고혈압"],
        "family_history": ["당뇨"],
        "medications": [
            {"condition": "고혈압", "name": "발사르탄", "dose": "80mg", "times_per_day": 1},
        ],
    },
    5: {
        "conditions": ["당뇨"],
        "family_history": [],
        "medications": [],
    },
}

_DEFAULT_MOCK_HEALTH_PROFILE: dict = {"conditions": [], "family_history": [], "medications": []}


class UserHealthContextService:
    def get_context(self, profile_id: int) -> dict:
        mock = _MOCK_HEALTH_PROFILES.get(profile_id, _DEFAULT_MOCK_HEALTH_PROFILE)
        return {
            "profile_id": profile_id,
            "conditions": mock["conditions"],
            "family_history": mock["family_history"],
            "medications": mock["medications"],
            "goals": [],
        }
