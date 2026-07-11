"""
T-LLM-2: 챗봇 LLM 프롬프트에 넘길 사용자 건강 컨텍스트 조립.

`app/services/llm_stub.py`가 이 dict를 그대로 문자열화(`f"{context}"`)해서 프롬프트에
박아넣으므로, 사람이 읽기 좋은 서술형 필드로 구성한다. `Profile`/복약 스케줄은 이미
호출자(`ChatService`)가 턴당 한 번만 조회해서 넘겨준다 — 여기서 추가 DB 조회는 하지 않는다.

[알려진 한계] `is_pregnant`는 항상 False다 — `Profile` 스키마에 임신 여부 필드가 없어서
판별할 방법이 없다(#71에서 스키마 추가 요청 중). 필드가 생기기 전까지 임부금기 DUR 경고는
구조적으로 비활성 상태다.

[중복 알림] 질환 한글 코드 매핑이 `ContentPersonalizationService`(T-LLM-3, PR #70)와
겹친다 — 스택 PR로 인한 머지 리스크를 피하려고 이번엔 의도적으로 중복시켰다. #70이 dev에
머지되면 공용 모듈로 추출해서 정리한다.
"""

from app.models.medication_model import MedicationSchedule
from app.models.profiles import Disease, Profile

_DISEASE_CODE_MAP: dict[str, str] = {
    Disease.CANCER.value: "암",
    Disease.HEART_DISEASE.value: "심장질환",
    Disease.CEREBROVASCULAR_DISEASE.value: "뇌혈관질환",
    Disease.DIABETES.value: "당뇨",
    Disease.LIVER_DISEASE.value: "간질환",
    Disease.OTHER.value: "기타",
}

_GERIATRIC_AGE_THRESHOLD = 65


def _map_diseases(entries: list[dict] | None) -> list[str]:
    if not entries:
        return []
    return list(dict.fromkeys(_DISEASE_CODE_MAP[e["disease"]] for e in entries if e.get("disease") in _DISEASE_CODE_MAP))


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
        return {
            "profile_id": profile.id,
            "name": profile.name,
            "conditions": _map_diseases(profile.diagnosis_history),
            "family_history": _map_diseases(profile.family_history),
            "medications": [
                {"name": m.medication.medication_name, "times_per_day": len(m.times)} for m in medications
            ],
            "goals": [],
            "is_pregnant": False,
            "is_geriatric": profile.age is not None and profile.age >= _GERIATRIC_AGE_THRESHOLD,
        }
