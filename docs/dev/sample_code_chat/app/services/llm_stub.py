"""
LLM 스트리밍 데모 — 실제로는 LangChain으로 감싼 LLM(개발: 저비용 모델 / 배포: Claude)을
토큰 단위로 스트리밍 호출하는 자리다 (decision_log.md "확정된 기술 결정" 표 참고).

⚠ 지금은 고정 문자열을 한 글자씩 흘려보내는 stub이다.
실제 연동 시에도 이 함수의 시그니처(Iterator[str] 반환)는 유지하고 내부 구현만 교체하면
ChatService/Router는 손대지 않아도 된다.
"""

from collections.abc import Iterator


def stream_llm_reply(message: str, context: dict, chunks: list[str]) -> Iterator[str]:
    reply = f"'{message}'에 대한 임시 응답입니다 (LLM 연동 전 stub, 참고 문서 {len(chunks)}건)."
    yield from reply
