"""
개발자가 로컬에서 1회 실행하는 오프라인 생성 스크립트. 5대 질환 x 3카테고리 콘텐츠를
LLM으로 생성해 JSON 픽스처 파일로 저장한다. DB에는 쓰지 않는다 — 생성된 파일을 git에
커밋해 팀 전체가 `seed_health_content.py`로 각자 로컬 DB에 채운다(OpenAI 키 없이도 가능).

실행: uv run python -m app.scripts.generate_health_content
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.services.content_service import CATEGORIES, POPULAR_DISEASES
from app.services.llm_stub import generate_content_card
from app.services.retriever_stub import Retriever

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "health_content_fixture.json"

ContentGenerator = Callable[[str, str, list[str]], Awaitable[dict]]


async def build_fixture_entries(retriever: Retriever, content_generator: ContentGenerator) -> list[dict]:
    entries = []
    for disease_code in POPULAR_DISEASES:
        for category in CATEGORIES:
            chunks = retriever.search(disease_code, {"disease_code": disease_code, "category": category})
            card = await content_generator(disease_code, category, chunks)
            entries.append({"disease_code": disease_code, "category": category, **card})
    return entries


async def _main() -> None:
    entries = await build_fixture_entries(Retriever(), generate_content_card)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(entries)}건 생성 완료 → {FIXTURE_PATH}")


if __name__ == "__main__":
    asyncio.run(_main())
