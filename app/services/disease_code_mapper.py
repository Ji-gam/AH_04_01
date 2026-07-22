"""
`Profile.diagnosis_history`/`family_history`(JSON, 영문 `Disease` enum 값)를 5대질환+기타
한글 disease_code로 매핑하는 공용 모듈. `ContentPersonalizationService`(T-LLM-3)와
`ChatContextService`(T-LLM-2)가 공유한다 — 저장 스키마가 바뀌어도(예: 조인 테이블 정규화)
여기만 고치면 되도록 한다.
"""

from app.models.profiles import Disease

DISEASE_CODE_MAP: dict[str, str] = {
    Disease.CANCER.value: "암",
    Disease.HEART_DISEASE.value: "심장질환",
    Disease.CEREBROVASCULAR_DISEASE.value: "뇌혈관질환",
    Disease.DIABETES.value: "당뇨",
    Disease.LIVER_DISEASE.value: "간질환",
    Disease.OTHER.value: "기타",
}


def map_diagnosis_entries(entries: list[dict] | None) -> list[str]:
    """diagnosis_history/family_history 항목 리스트를 한글 disease_code 리스트로 변환한다.
    매핑 안 되는 값은 조용히 제외하고, 중복은 제거하되 순서는 유지한다."""
    if not entries:
        return []
    return list(dict.fromkeys(DISEASE_CODE_MAP[e["disease"]] for e in entries if e.get("disease") in DISEASE_CODE_MAP))


_REVERSE_DISEASE_CODE_MAP: dict[str, Disease] = {v: Disease(k) for k, v in DISEASE_CODE_MAP.items()}


def disease_code_to_enum(disease_code: str) -> Disease | None:
    """한글 disease_code(health_contents.disease_code)를 다시 Disease enum으로 되돌린다 -
    콘텐츠 알림(content_notification_service.py)이 "이 질환을 진단병력에 등록한 사람"을
    찾을 때 쓴다. 매핑 안 되는 값(구성 데이터 오류 등)은 None."""
    return _REVERSE_DISEASE_CODE_MAP.get(disease_code)
