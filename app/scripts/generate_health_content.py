"""
개발자가 로컬에서 1회 실행하는 오프라인 생성 스크립트. 5대 질환 x 3카테고리 콘텐츠를
LLM으로 생성해 JSON 픽스처 파일로 저장한다. DB에는 쓰지 않는다 — 생성된 파일을 git에
커밋해 팀 전체가 `seed_health_content.py`로 각자 로컬 DB에 채운다(OpenAI 키 없이도 가능).

T-LLM-2-async-gateway: 실제 생성은 `AIWorkerGateway.call_structured()`를 통해 `ai_worker`가
담당한다(RAG 그라운딩은 이번 라운드 미적용 — Chroma 인덱스가 성분명 기준이라 질환 기준
검색과 맞지 않기 때문. `_genies_task.md` 참고).

실행: uv run python -m app.scripts.generate_health_content
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel

from app.services.ai_worker_gateway import AIWorkerGateway
from app.services.content_service import CATEGORIES, CATEGORY_TOPICS, POPULAR_DISEASES, _today_kst

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "health_content_fixture.json"

ContentGenerator = Callable[[str, str, str], Awaitable[dict]]


class HealthContentCard(BaseModel):
    title: str
    summary: str
    body: str
    image_prompt: str | None = None


async def generate_content_card(disease_code: str, category: str, topic: str) -> dict:
    """`AIWorkerGateway.call_structured()`로 질환+카테고리+소주제 하나에 대한 건강 콘텐츠
    카드를 생성한다. 프롬프트/스키마는 이 도메인(콘텐츠 생성)이 직접 소유한다 — Gateway는
    이를 대신하지 않는다.

    "기타"(5대질환에 안 걸리는 질환 등록자용)는 특정 질환을 짚을 수 없으므로, 질환 특정이
    아닌 일반적인 건강관리 팁으로 생성한다."""
    gateway = AIWorkerGateway()
    system_prompt = (
        "당신은 ReMedi의 건강 콘텐츠 작가입니다. 주어진 질환과 카테고리, 세부 주제에 맞는 짧고 실용적인 건강 팁 카드를 작성하세요."
    )
    subject = "특정 질환에 한정되지 않는 일반적인 건강관리 정보" if disease_code == "기타" else f"질환: {disease_code}"
    user_input = f"{subject}, 카테고리: {category}, 세부 주제: {topic}"
    card = await gateway.call_structured(
        system_prompt=system_prompt,
        user_input=user_input,
        schema=HealthContentCard,
    )
    return card.model_dump()


async def build_fixture_entries(content_generator: ContentGenerator) -> list[dict]:
    """질환 x 카테고리마다 `CATEGORY_TOPICS`의 소주제 3개를 각각 생성해 "정보" 탭에서
    장르당 최소 3장이 보이게 한다. 같은 (질환, 카테고리) 안에서 유니크 제약을 지키면서
    공존하도록, 소주제 순서대로 하루씩 과거로 backdate한 `content_date`를 함께 기록한다
    (조회 API는 날짜로 거르지 않으므로 화면에는 3장 모두 그대로 보인다)."""
    today = _today_kst()
    entries = []
    for disease_code in POPULAR_DISEASES:
        for category in CATEGORIES:
            for offset, topic in enumerate(CATEGORY_TOPICS[category]):
                card = await content_generator(disease_code, category, topic)
                entries.append(
                    {
                        "disease_code": disease_code,
                        "category": category,
                        "content_date": (today - timedelta(days=offset)).isoformat(),
                        **card,
                    }
                )
    return entries


async def _main() -> None:
    entries = await build_fixture_entries(generate_content_card)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(entries)}건 생성 완료 → {FIXTURE_PATH}")


if __name__ == "__main__":
    asyncio.run(_main())
