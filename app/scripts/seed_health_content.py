"""
`generate_health_content.py`가 만든 JSON 픽스처를 로컬 DB에 채우는 스크립트.
OpenAI 키가 없는 팀원도 이 스크립트만 실행하면 "정보" 탭 데모 콘텐츠를 볼 수 있다.
오늘 날짜 기준으로 시드하므로, 다음날 다시 보려면 재실행이 필요하다(당일 캐시 설계).

실행: uv run python -m app.scripts.seed_health_content
"""

import asyncio
import json

from app.core.db.databases import AsyncSessionLocal
from app.scripts.generate_health_content import FIXTURE_PATH
from app.services.content_service import ContentService


async def _main() -> None:
    entries = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    async with AsyncSessionLocal() as session:
        inserted = await ContentService().seed_from_fixture(session, entries)
        print(f"{inserted}건 신규 시드 완료 (이미 오늘자 캐시가 있는 조합은 건너뜀)")


if __name__ == "__main__":
    asyncio.run(_main())
