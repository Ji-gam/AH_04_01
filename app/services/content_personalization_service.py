"""
T-LLM-3: 컨텐츠 개인화 판단 전담 모듈.
`Profile.diagnosis_history`(JSON, 영문 `Disease` enum 값)를 컨텐츠 조회에 쓰는 한글
disease_code로 변환한다. 이 매핑을 이 클래스 안에만 가둬서, 저장 스키마가 바뀌어도
(예: 조인 테이블로 정규화) 여기만 고치면 되도록 한다.

`Profile` 객체는 라우터의 인증 의존성이 이미 조회해 로드해 둔 것을 그대로 받는다 —
여기서 별도로 DB를 다시 조회하지 않는다.
"""

from app.models.profiles import Disease, Profile

_DISEASE_CODE_MAP: dict[str, str] = {
    Disease.CANCER.value: "암",
    Disease.HEART_DISEASE.value: "심장질환",
    Disease.CEREBROVASCULAR_DISEASE.value: "뇌혈관질환",
    Disease.DIABETES.value: "당뇨",
    Disease.LIVER_DISEASE.value: "간질환",
    Disease.OTHER.value: "기타",
}


class ContentPersonalizationService:
    def resolve(self, profile: Profile | None) -> tuple[bool, list[str] | None]:
        """(personalized, diseases)를 반환한다.
        비로그인이거나 등록된 질환이 없으면 (False, None) — 전체 콘텐츠 폴백 신호."""
        if profile is None or not profile.diagnosis_history:
            return False, None
        diseases = list(
            dict.fromkeys(
                _DISEASE_CODE_MAP[entry["disease"]]
                for entry in profile.diagnosis_history
                if entry.get("disease") in _DISEASE_CODE_MAP
            )
        )
        if not diseases:
            return False, None
        return True, diseases
