"""
LLM 스트리밍 — `OPENAI_API_KEY`가 설정되어 있으면 실제 OpenAI(`OPENAI_MODEL`, 기본
gpt-4o-mini)를 토큰 단위로 스트리밍 호출하고, 없으면 고정 문자열 stub으로 폴백한다
(로컬 개발 시 API 키 없이도 계속 동작). `docs/decision_log.md` "AH_04_01 이관 시
변경된 결정" 표 참고 — 배포 시 모델 재검토는 별도 결정 사항이다.

이 함수의 시그니처(AsyncIterator[str] 반환)는 유지하고 내부 구현만 교체하면
ChatService/Router는 손대지 않아도 된다(CODING_RULES.md 8번 Tier 2 stub 패턴).
"""

import json
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
        "이 시스템은 답변 하단 UI 영역에 면책 조항(의사와 상담하라는 내용 등)을 별도로 노출하고 있습니다.\n"
        "따라서 당신의 답변 본문 텍스트 내에는 '의사와 상담하세요', '의학적 조언이 아닙니다' 같은 자가 경고나 면책 문구를 절대 적지 마십시오.\n"
        "오직 사용자의 질문에 대한 핵심 의학적 정보와 대답만을 정확하고 팩트 기반으로 답변하세요.\n"
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


async def generate_content_card(disease_code: str, category: str, chunks: list[dict]) -> dict:
    """T-LLM-3: 질환+카테고리 하나에 대한 건강 콘텐츠 카드를 JSON으로 생성한다.
    `stream_llm_reply`(T-LLM-2, 스트리밍 챗봇 응답)와는 별개 함수로, 기존 챗봇 흐름에는
    영향을 주지 않는 추가 함수다."""
    if _client is None:
        return {
            "title": f"{disease_code} {category} 안내 (stub)",
            "summary": f"{disease_code}에 대한 {category} 카테고리 임시 요약입니다.",
            "body": f"'{disease_code}'의 {category} 카테고리 임시 본문입니다 (LLM 연동 전 stub, 참고 문서 {len(chunks)}건).",
            "image_prompt": None,
        }

    system_prompt = (
        "당신은 ReMedi의 건강 콘텐츠 작가입니다. 주어진 질환과 카테고리에 맞는 짧은 건강 팁 카드를 "
        "생성하세요. 반드시 title, summary, body, image_prompt 키만 가진 JSON 객체로만 응답하세요.\n"
        f"참고 문서: {chunks}"
    )
    response = await _client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"질환: {disease_code}, 카테고리: {category}"},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content) if content else {}
