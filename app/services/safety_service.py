"""
공통모듈 — 안전 프롬프트/면책조항 정책 (T-LLM-1).
`docs/squad-map.md` 2번 표 대상 — 담당자 미지정 구간이므로 신규 LLM 기능 개발자는
반드시 이 파일의 `apply_disclaimer`를 거쳐 응답을 반환해야 T-LLM-1 성공요건을 만족한다.
"""

DISCLAIMER_TEXT = "이 정보는 의학적 조언이 아니며, 정확한 진단은 의료진과 상담하세요."


def apply_disclaimer(reply: str) -> str:
    return f"{reply}\n\n{DISCLAIMER_TEXT}"
