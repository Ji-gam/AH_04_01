"""T-LLM-6 수동 트리거: 등록된 모든 매체를 1회 수집하고, 요약이 빈 기사의 카드뉴스 요약을 만든다.

두 단계로 나눠 실행한다 - 기사를 먼저 다 저장한 뒤 요약을 채우므로, OpenAI가 흔들려도
기사 수집은 남는다. 요약을 못 만든 기사는 다음 실행에서 자동으로 다시 시도된다.

주기 자동 수집(Celery)은 나중이다 - 지금 docker-compose에는 Celery worker/beat 서비스가
아예 없어서 코드만으로는 안 된다(리더 승인 필요, 계획 문서 6절 참고). 그때까지는 이 스크립트와
관리자 화면의 [뉴스 수집] 버튼이 트리거 역할을 한다.

같은 피드를 여러 번 실행해도 안전하다 - 이미 저장된 기사는 건너뛰고, 이미 요약이 있는 기사는
다시 생성하지 않는다(멱등).

실행: uv run python -m app.scripts.collect_health_news
      uv run python -m app.scripts.collect_health_news --skip-summary   # 수집만
      uv run python -m app.scripts.collect_health_news --regenerate-summaries  # 수집 없이 요약만 전체 재생성
"""

import argparse
import asyncio
from dataclasses import dataclass

from app.core.db.databases import AsyncSessionLocal
from app.services.health_news_service import CollectResult, HealthNewsService, SummaryResult


@dataclass
class BatchTotals:
    """배치를 여러 번 돌린 합계. 관리자 화면과 달리 여기는 끝까지 다 돌린다."""

    attempted: int = 0
    generated: int = 0
    failed: int = 0
    rounds: int = 0
    first_error: str | None = None
    # 남았는데 더 못 진행하고 멈춘 수. 0이 정상이다.
    gave_up_with: int = 0

    def absorb(self, result: SummaryResult) -> None:
        self.attempted += result.pending
        self.generated += result.generated
        self.failed += result.failed
        self.rounds += 1
        if self.first_error is None:
            self.first_error = result.first_error


async def fill_card_summaries() -> BatchTotals:
    """요약이 없는 기사를 **끝까지** 채운다.

    서비스는 한 번에 한 배치만 만든다(관리자 화면의 게이트웨이 타임아웃 때문). 여기는 HTTP를
    타지 않으므로 `remaining`이 0이 될 때까지 이어서 돌린다.

    **진행이 없으면 멈춘다** - 같은 기사가 계속 실패하는 상황에서 이어 돌리면 무한 반복이다.
    """
    totals = BatchTotals()
    service = HealthNewsService()
    async with AsyncSessionLocal() as session:
        while True:
            result = await service.generate_missing_card_summaries(session)
            totals.absorb(result)
            if result.remaining == 0:
                return totals
            if result.generated == 0:
                # 남았지만 한 건도 못 만들었다 - 다시 돌려도 같은 결과다.
                totals.gave_up_with = result.remaining
                return totals


async def collect_health_news(*, with_summary: bool = True) -> tuple[CollectResult, BatchTotals | None]:
    service = HealthNewsService()
    async with AsyncSessionLocal() as session:
        collected = await service.collect_all(session)
    if not with_summary:
        return collected, None
    return collected, await fill_card_summaries()


async def regenerate_card_summaries() -> BatchTotals:
    """수집 없이 **모든** 기사의 카드요약을 다시 만든다. 관리자 화면의
    [카드요약 다시 만들기] 버튼과 같은 일을 한다 - 프롬프트나 글자 수 제한을 손질한 뒤
    기존 기사에도 새 기준을 적용할 때 쓴다.

    재생성은 요약이 이미 있는 기사도 대상이라 진행 위치가 데이터에 남지 않는다 - 그래서
    `offset`을 직접 옮겨가며 끝까지 돌린다."""
    totals = BatchTotals()
    service = HealthNewsService()
    offset = 0
    async with AsyncSessionLocal() as session:
        while True:
            result = await service.regenerate_card_summaries(session, offset=offset)
            totals.absorb(result)
            # 실패한 기사도 지나간 것으로 센다 - 여기서 멈춰 서면 같은 기사를 영원히 다시 시도한다.
            offset += result.pending
            if result.remaining == 0 or result.pending == 0:
                return totals


async def _main() -> None:
    parser = argparse.ArgumentParser(description="건강 뉴스 수집 + 카드요약 생성")
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="수집만 하고 카드요약은 만들지 않는다(LLM 비용 없이 수집만 확인할 때)",
    )
    parser.add_argument(
        "--regenerate-summaries",
        action="store_true",
        help="수집하지 않고, 저장된 모든 기사의 카드요약을 다시 만든다(프롬프트를 손질한 뒤에 쓴다)",
    )
    args = parser.parse_args()

    if args.regenerate_summaries:
        regenerated = await regenerate_card_summaries()
        print(
            f"[카드요약 재생성] 기사 {regenerated.attempted}건 중 "
            f"{regenerated.generated}건 다시 생성, {regenerated.failed}건 실패(기존 요약 유지) "
            f"- {regenerated.rounds}배치"
        )
        if regenerated.first_error:
            print(f"[실패 원인] {regenerated.first_error}")
        return

    collected, summarized = await collect_health_news(with_summary=not args.skip_summary)
    print(
        f"[수집] 피드 {collected.fetched}건 중 "
        f"신규 {collected.created}건 저장, "
        f"{collected.skipped}건 이미 있어 건너뜀, "
        f"{collected.excluded}건 건강정보 아니어서 제외, "
        f"{collected.over_limit}건 매체당 상한으로 미룸, "
        f"{collected.unreadable}건 본문 추출 실패"
    )
    if collected.first_error:
        print(f"[수집 실패 원인] {collected.first_error}")
    if summarized is None:
        print("[카드요약] --skip-summary 지정으로 건너뜀")
    else:
        print(
            f"[카드요약] 요약 없던 {summarized.attempted}건 중 "
            f"{summarized.generated}건 생성, {summarized.failed}건 실패(다음 실행에서 재시도) "
            f"- {summarized.rounds}배치"
        )
        if summarized.gave_up_with:
            print(f"[카드요약] {summarized.gave_up_with}건이 남았지만 진행이 없어 멈췄습니다 - 아래 원인을 보세요")
        if summarized.first_error:
            print(f"[카드요약 실패 원인] {summarized.first_error}")


if __name__ == "__main__":
    asyncio.run(_main())
