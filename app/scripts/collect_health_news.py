"""T-LLM-6 수동 트리거: 코메디닷컴 RSS를 1회 수집하고, 요약이 빈 기사의 카드뉴스 요약을 만든다.

두 단계로 나눠 실행한다 - 기사를 먼저 다 저장한 뒤 요약을 채우므로, OpenAI가 흔들려도
기사 수집은 남는다. 요약을 못 만든 기사는 다음 실행에서 자동으로 다시 시도된다.

주기 자동 수집(Celery)은 나중이다 - 지금 docker-compose에는 Celery worker/beat 서비스가
아예 없어서 코드만으로는 안 된다(리더 승인 필요, 계획 문서 6절 참고). 그때까지는 이 스크립트와
관리자 화면의 [뉴스 수집] 버튼이 트리거 역할을 한다.

같은 피드를 여러 번 실행해도 안전하다 - 이미 저장된 기사는 건너뛰고, 이미 요약이 있는 기사는
다시 생성하지 않는다(멱등).

실행: uv run python -m app.scripts.collect_health_news
      uv run python -m app.scripts.collect_health_news --skip-summary   # 수집만
"""

import argparse
import asyncio

from app.core.db.databases import AsyncSessionLocal
from app.services.health_news_service import CollectResult, HealthNewsService, SummaryResult
from app.services.health_news_source import KORMEDI


async def collect_health_news(*, with_summary: bool = True) -> tuple[CollectResult, SummaryResult | None]:
    service = HealthNewsService()
    async with AsyncSessionLocal() as session:
        collected = await service.collect(session, KORMEDI)
        if not with_summary:
            return collected, None
        summarized = await service.generate_missing_card_summaries(session)
    return collected, summarized


async def _main() -> None:
    parser = argparse.ArgumentParser(description="건강 뉴스 수집 + 카드요약 생성")
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="수집만 하고 카드요약은 만들지 않는다(LLM 비용 없이 수집만 확인할 때)",
    )
    args = parser.parse_args()

    collected, summarized = await collect_health_news(with_summary=not args.skip_summary)
    print(
        f"[수집] RSS {collected.fetched}건 중 "
        f"신규 {collected.created}건 저장, "
        f"{collected.skipped}건 이미 있어 건너뜀, "
        f"{collected.excluded}건 건강정보 아니어서 제외"
    )
    if summarized is None:
        print("[카드요약] --skip-summary 지정으로 건너뜀")
    else:
        print(
            f"[카드요약] 요약 없던 {summarized.pending}건 중 "
            f"{summarized.generated}건 생성, {summarized.failed}건 실패(다음 실행에서 재시도)"
        )


if __name__ == "__main__":
    asyncio.run(_main())
