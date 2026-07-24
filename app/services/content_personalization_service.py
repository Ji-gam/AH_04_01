"""
T-LLM-3: 컨텐츠 개인화 판단 전담 모듈.
[정규화] `Profile.diagnosis_history`(JSON)가 `diagnosis_entries` 테이블(1:N 관계)로 바뀌면서,
`disease_code_mapper.map_diagnosis_entries`가 원래 기대하던 `list[dict]`(예:
`[{"disease": "DIABETES"}]`) 형태로 변환해서 넘긴다 - `disease_code_mapper` 자체는 안 건드린다
(chat_context_service와 공유하는 공용 모듈이라, 호출부에서만 형태를 맞춰준다).
`Profile` 객체는 라우터의 인증 의존성이 이미 조회해 로드해 둔 것을 그대로 받는다 —
여기서 별도로 DB를 다시 조회하지 않는다.
"""

from app.models.profiles import Profile
from app.services.disease_code_mapper import map_diagnosis_entries


class ContentPersonalizationService:
    def resolve(self, profile: Profile | None) -> tuple[bool, list[str] | None]:
        """(personalized, diseases)를 반환한다.
        비로그인이거나 등록된 질환이 없으면 (False, None) — 전체 콘텐츠 폴백 신호."""
        if profile is None or not profile.diagnosis_entries:
            return False, None
        entries = [{"disease": e.disease.value} for e in profile.diagnosis_entries]
        diseases = map_diagnosis_entries(entries)
        if not diseases:
            return False, None
        return True, diseases
