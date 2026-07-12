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

# 공백 제거 후 부분 문자열로 매칭하는 단일 응급 표현.
# 한국어 조사/어미 변형을 전부 열거할 수 없으므로, 어미가 붙어도 살아남는 어간 위주로 둔다
# (예: "쓰러" → 쓰러졌다/쓰러질 것 같다 모두 매칭).
_EMERGENCY_KEYWORDS = (
    "흉통",
    "호흡곤란",
    "심장마비",
    "심정지",
    "각혈",
    "실신",
    "의식이없",
    "의식없",
    "의식을잃",
    "의식잃",
    "정신을잃",
    "정신잃",
    "쓰러",
    "경련",
    "발작",
    "자살",
    "죽고싶",
    "극단적선택",
    "목을매",
)

# 신체부위 어간 + 증상 어간이 함께 있을 때만 응급으로 판정한다(오탐 최소화).
# 응급 폴백은 정상 답변을 가로채므로, 부위/증상 단독으로는 트리거하지 않는다.
_EMERGENCY_COMBINATIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("가슴",), ("아파", "아프", "답답", "조여", "쥐어", "짓눌", "통증")),
    (("숨",), ("안쉬", "못쉬", "쉬기힘", "차올", "막힌", "막혀", "가빠", "가쁘", "안쉼")),
)


def _normalize(text: str) -> str:
    """공백을 모두 제거해 "가슴 통증"과 "가슴통증"을 동일하게 취급한다."""
    return "".join(text.split())


def apply_disclaimer(reply: str) -> str:
    return f"{reply}\n\n{DISCLAIMER_TEXT}"


def check_emergency(message: str) -> bool:
    normalized = _normalize(message)
    if any(keyword in normalized for keyword in _EMERGENCY_KEYWORDS):
        return True
    for parts, symptoms in _EMERGENCY_COMBINATIONS:
        if all(part in normalized for part in parts) and any(symptom in normalized for symptom in symptoms):
            return True
    return False
