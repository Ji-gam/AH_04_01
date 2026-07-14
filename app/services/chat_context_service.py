"""
T-LLM-2: 챗봇 LLM 프롬프트에 넘길 사용자 건강 컨텍스트 조립.
`app/services/llm_stub.py`가 이 dict를 그대로 문자열화(`f"{context}"`)해서 프롬프트에
박아넣으므로, 사람이 읽기 좋은 서술형 필드로 구성한다. `Profile`/복약 스케줄은 이미
호출자(`ChatService`)가 턴당 한 번만 조회해서 넘겨준다 — 여기서 추가 DB 조회는 하지 않는다.
[알려진 한계] `is_pregnant`는 항상 False다 — `Profile` 스키마에 임신 여부 필드가 없어서
판별할 방법이 없다(#71에서 스키마 추가 요청 중). 필드가 생기기 전까지 임부금기 DUR 경고는
구조적으로 비활성 상태다.
질환 한글 코드 매핑은 `disease_code_mapper`가 전담한다 — `ContentPersonalizationService`
(T-LLM-3)와 공유한다.
[정규화] `Profile.diagnosis_history`/`family_history`(JSON)가 `diagnosis_entries`/
`family_history_entries` 테이블(1:N 관계)로 바뀌면서, `disease_code_mapper`가 기대하는
`list[dict]` 형태로 변환해서 넘긴다 - `disease_code_mapper` 자체는 안 건드린다.
"""

from app.models.medication_model import MedicationSchedule
from app.models.profiles import Profile
from app.services.disease_code_mapper import map_diagnosis_entries

_GERIATRIC_AGE_THRESHOLD = 65


class ChatContextService:
    def build(self, profile: Profile | None, medications: list[MedicationSchedule]) -> dict:
        if profile is None:
            return {
                "profile_id": None,
                "name": "사용자",
                "conditions": [],
                "family_history": [],
                "medications": [],
                "goals": [],
                "is_pregnant": False,
                "is_geriatric": False,
            }
        conditions = [{"disease": e.disease.value} for e in profile.diagnosis_entries]
        family_history = [{"disease": e.disease.value} for e in profile.family_history_entries]
        return {
            "profile_id": profile.id,
            "name": profile.name,
            "conditions": map_diagnosis_entries(conditions),
            "family_history": map_diagnosis_entries(family_history),
            "medications": [{"name": m.medication.medication_name, "times_per_day": len(m.times)} for m in medications],
            "goals": [],
            "is_pregnant": False,
            "is_geriatric": profile.age is not None and profile.age >= _GERIATRIC_AGE_THRESHOLD,
        }
