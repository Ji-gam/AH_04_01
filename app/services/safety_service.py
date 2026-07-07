"""
공통모듈 — 안전 프롬프트/면책조항 정책(T-LLM-1) + 응급 키워드 감지(T-LLM-2).
`docs/squad-map.md` 2번 표 대상 — 담당자 미지정 구간이므로 신규 LLM 기능 개발자는
반드시 이 파일의 `apply_disclaimer`를 거쳐 응답을 반환해야 T-LLM-1 성공요건을 만족한다.

판단은 여기서만 한다. Router/Service는 이 함수들만 호출하고 키워드 목록 관리는
이 파일 안에서 끝낸다(`docs/dev/sample_code_chat/app/services/safety_service.py` 패턴).
"""

DISCLAIMER_TEXT = "이 정보는 의학적 조언이 아니며, 정확한 진단은 의료진과 상담하세요."

EMERGENCY_FALLBACK_MESSAGE = (
    "긴급한 증상일 수 있습니다. 즉시 119(응급실) 또는 자살예방상담전화 1393으로 연락하세요. "
    "이 답변은 의학적 조언이 아닙니다."
)

_EMERGENCY_KEYWORDS = ["가슴 통증", "숨이 안 쉬어져", "의식이 없어요"]


def apply_disclaimer(reply: str) -> str:
    return f"{reply}\n\n{DISCLAIMER_TEXT}"


def check_emergency(message: str) -> bool:
    return any(keyword in message for keyword in _EMERGENCY_KEYWORDS)
