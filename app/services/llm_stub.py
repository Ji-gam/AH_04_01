"""
LLM 스트리밍 — `OPENAI_API_KEY`가 설정되어 있으면 실제 OpenAI(`OPENAI_MODEL`, 기본
gpt-4o-mini)를 토큰 단위로 스트리밍 호출하고, 없으면 고정 문자열 stub으로 폴백한다
(로컬 개발 시 API 키 없이도 계속 동작). `docs/decision_log.md` "AH_04_01 이관 시
변경된 결정" 표 참고 — 배포 시 모델 재검토는 별도 결정 사항이다.

이 함수의 시그니처(AsyncIterator[str] 반환)는 유지하고 내부 구현만 교체하면
ChatService/Router는 손대지 않아도 된다(CODING_RULES.md 8번 Tier 2 stub 패턴).
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core import config

_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else None


async def _stream_stub_reply(message: str, chunks: list[str]) -> AsyncIterator[str]:
    reply = f"'{message}'에 대한 임시 응답입니다 (LLM 연동 전 stub, 참고 문서 {len(chunks)}건)."
    for char in reply:
        yield char


async def stream_llm_reply(message: str, context: dict, chunks: list[str]) -> AsyncIterator[str]:
    if _client is None:
        async for char in _stream_stub_reply(message, chunks):
            yield char
        return

    system_prompt = (
        "당신은 ReMedi의 건강 상담 챗봇입니다. 아래 사용자 건강 컨텍스트(진단병력·가족력·"
        "복약정보)를 참고해 개인화된 답변을 간결하고 안전하게 제공하세요.\n"
        f"참고 문서: {chunks}\n"
        f"사용자 건강 컨텍스트: {context}"
    )
    stream = await _client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        stream=True,
    )
    async for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta
