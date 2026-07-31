"""
공통① 응급필터 + 면책정책 (T-LLM-1, T-LLM-2 관련) 데모.
실제 위치: app/services/safety_service.py — 공통모듈이므로 소유자 지정 필요 (`docs/squad-map.md`).

판단은 여기서만 한다. Router/Service는 이 함수만 호출하고 키워드 목록 관리는 이 파일 안에서 끝낸다.
"""

EMERGENCY_FALLBACK_MESSAGE = (
    "긴급한 증상일 수 있습니다. 즉시 119(응급실) 또는 자살예방상담전화 1393으로 연락하세요. "
    "이 답변은 의학적 조언이 아닙니다."
)

_EMERGENCY_KEYWORDS = ["가슴 통증", "숨이 안 쉬어져", "의식이 없어요"]


def check_emergency(message: str) -> bool:
    return any(keyword in message for keyword in _EMERGENCY_KEYWORDS)
