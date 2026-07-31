"""
T-LLM-2: 챗봇 LLM 프롬프트에 넘길 사용자 건강 컨텍스트 조립.
T-LLM-7-3-2: 이 dict는 `ChatService`가 `ai_worker`의 `/agent/chat`으로 그대로 넘기고,
`ai_worker/tasks/chat_agent.py`가 문자열화(`f"{context}"`)해서 프롬프트에 박아넣는다
(LLM 호출 자체가 app/에서 ai_worker로 옮겨감 — 이전엔 app/services/llm_stub.py가 담당).
사람이 읽기 좋은 서술형 필드로 구성한다. `Profile`/복약 스케줄은 이미 호출자(`ChatService`)가
턴당 한 번만 조회해서 넘겨준다 — 여기서 추가 DB 조회는 하지 않는다.
[#71 해결] `is_pregnant`는 이제 `Profile.is_pregnant`(개인건강정보에서 선택 입력)로부터
실제 값을 읽는다 - 미입력(None)이면 모르는 상태이므로 임부금기 DUR 경고 게이팅에서는
False로 취급한다(구조적으로 "모른다"와 "아니다"를 다르게 다루고 싶으면 이 부분만 고치면 됨).
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
    def build(
        self, profile: Profile | None, medications: list[MedicationSchedule], drug_names: dict[str, str] | None = None
    ) -> dict:
        """(T-MED-16) `medications`는 이제 item_seq만 들고 있어(마스터 데이터 캐시 테이블이 없어짐),
        약품명이 필요하면 호출자가 미리 `DurDrugRepository.get_names_by_item_seqs`로 조회해
        `drug_names`로 넘겨야 한다 - 여기서는 여전히 추가 DB 조회를 하지 않는다."""
        drug_names = drug_names or {}
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
            "medications": [
                {"name": m.display_name or drug_names.get(m.item_seq, m.item_seq), "times_per_day": len(m.times)}
                for m in medications
            ],
            "goals": [],
            "is_pregnant": bool(profile.health_profile.is_pregnant) if profile.health_profile else False,
            "is_geriatric": profile.age is not None and profile.age >= _GERIATRIC_AGE_THRESHOLD,
        }
