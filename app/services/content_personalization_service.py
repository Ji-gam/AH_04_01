"""
T-LLM-3: 컨텐츠 개인화 판단 전담 모듈.
`Profile.diagnosis_history`(JSON, 영문 `Disease` enum 값)를 컨텐츠 조회에 쓰는 한글
disease_code로 변환한다. 매핑 자체는 `disease_code_mapper`(chat_context_service와 공유)가
전담한다.

`Profile` 객체는 라우터의 인증 의존성이 이미 조회해 로드해 둔 것을 그대로 받는다 —
여기서 별도로 DB를 다시 조회하지 않는다.
"""

from app.models.profiles import Profile
from app.services.disease_code_mapper import map_diagnosis_entries


class ContentPersonalizationService:
    def resolve(self, profile: Profile | None) -> tuple[bool, list[str] | None]:
        """(personalized, diseases)를 반환한다.
        비로그인이거나 등록된 질환이 없으면 (False, None) — 전체 콘텐츠 폴백 신호."""
        if profile is None or not profile.diagnosis_history:
            return False, None
        diseases = map_diagnosis_entries(profile.diagnosis_history)
        if not diseases:
            return False, None
        return True, diseases
