"""T-LLM-6: 수집 오케스트레이션. RSS 파서(`health_news_source`)와 저장소를 이어붙인다.

**수집과 카드요약은 두 단계로 나눠 실행한다.** 카드요약은 LLM에 의존해 느리고 실패할 수 있어서,
한 몸으로 묶으면 OpenAI가 흔들릴 때 기사 저장까지 같이 실패한다. 그래서
`collect()`로 기사를 먼저 다 저장하고, `generate_missing_card_summaries()`가 요약이 빈 기사만
따로 채운다 - 중간에 실패해도 다음 실행이 빠진 것만 다시 시도한다.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.health_news_dto import (
    CardSummary,
    HealthNewsDetailResponse,
    HealthNewsFeedItem,
)
from app.models.health_news import HealthNews
from app.repositories.health_news_repository import HealthNewsRepository
from app.services import health_news_card_summary, health_news_source
from app.services.health_news_source import ParsedArticle
from app.services.safety_service import DISCLAIMER_TEXT

logger = logging.getLogger(__name__)

# 피드 한 번에 내려줄 기본 개수. 기사가 쌓여도 첫 화면이 무거워지지 않게 상한을 둔다.
DEFAULT_FEED_LIMIT = 30


@dataclass
class CollectResult:
    """수집 1회의 결과. 관리자 화면이 이 숫자를 그대로 보여준다."""

    fetched: int  # RSS에서 파싱된 기사 수
    excluded: int  # 건강정보가 아닌 카테고리라 버린 수
    created: int  # 새로 저장한 수
    skipped: int  # 이미 있어서 건너뛴 수


@dataclass
class SummaryResult:
    """카드요약 생성 1회의 결과."""

    pending: int  # 요약이 비어 있던 기사 수
    generated: int  # 새로 요약을 채운 수
    failed: int  # LLM 실패로 못 채운 수(다음 실행에서 재시도된다)


class HealthNewsService:
    def __init__(self, repo: HealthNewsRepository | None = None) -> None:
        self._repo = repo or HealthNewsRepository()

    async def collect(self, session: AsyncSession, source: health_news_source.NewsSourceDef) -> CollectResult:
        """매체 하나를 1회 수집한다. 관리자 [뉴스 수집] 버튼과 수동 트리거 스크립트가 같이 호출한다.
        어떤 매체인지는 인자로 받는다 - 소스가 늘어도(7단계) 이 메서드는 그대로다."""
        fetched = await health_news_source.fetch(source)
        saved = await self._save_articles(session, fetched.articles)
        return CollectResult(
            fetched=len(fetched.articles) + fetched.excluded,
            excluded=fetched.excluded,
            created=saved.created,
            skipped=saved.skipped,
        )

    async def _save_articles(self, session: AsyncSession, articles: list[ParsedArticle]) -> CollectResult:
        """이미 있는 기사(source + source_url)는 건너뛴다.

        DB 유니크 제약이 최종 방어선이지만, 조회로 먼저 걸러서 건너뛴 수를 세고 무의미한
        INSERT 실패를 만들지 않는다. 같은 RSS를 몇 번 돌려도 결과가 같아야 한다(멱등)."""
        created = 0
        skipped = 0
        for article in articles:
            existing = await self._repo.get_by_source_url(session, article.source, article.source_url)
            if existing is not None:
                skipped += 1
                continue
            await self._repo.save(
                session,
                source=article.source,
                source_name=article.source_name,
                source_url=article.source_url,
                title=article.title,
                published_at=article.published_at,
                body_text=article.body_text,
                image_url=article.image_url,
                image_caption=article.image_caption,
                source_categories=article.source_categories,
            )
            created += 1
        # fetched/excluded는 호출자(collect)가 채운다 - 여기는 걸러진 뒤의 목록만 받으므로
        # 원래 몇 건이었는지 모른다.
        return CollectResult(fetched=len(articles), excluded=0, created=created, skipped=skipped)

    async def generate_missing_card_summaries(self, session: AsyncSession, limit: int | None = None) -> SummaryResult:
        """카드요약이 아직 없는 기사들의 요약을 만들어 채운다.

        기사 한 건이 실패해도 나머지는 계속 처리한다 - 한 건의 LLM 오류로 배치 전체가 멈추면
        그날 수집분이 통째로 요약 없는 상태가 된다. 실패한 기사는 `card_summary`가 그대로
        비어 있으므로 다음 실행에서 자동으로 다시 시도된다."""
        pending = await self._repo.list_missing_card_summary(session, limit=limit)
        generated = 0
        failed = 0
        for news in pending:
            try:
                summary = await health_news_card_summary.generate_card_summary(news)
            except Exception:
                # 실패 원인(LLM 응답 형식, OpenAI 장애, 스키마 하한 미달 등)을 남기고 다음 기사로.
                logger.exception("카드요약 생성 실패 (news_id=%s)", news.id)
                failed += 1
                continue
            await self._repo.set_card_summary(session, news, summary.model_dump())
            generated += 1
        return SummaryResult(pending=len(pending), generated=generated, failed=failed)

    # ── 조회 ──────────────────────────────────────────────────────────────────

    async def get_feed(self, session: AsyncSession, limit: int | None = None) -> list[HealthNewsFeedItem]:
        """건강정보 화면의 뉴스 피드. 1단계는 개인화 없이 발행일 최신순이다(질환 태깅은 2단계).

        요약이 아직 없는 기사도 피드에는 보여준다 - 원문은 이미 읽을 수 있으므로 감출 이유가
        없고, `has_card_summary`로 [카드요약보기] 버튼만 비활성으로 두면 된다."""
        rows = await self._repo.list_feed(session, limit=limit or DEFAULT_FEED_LIMIT)
        return [
            HealthNewsFeedItem(
                id=n.id,
                title=n.title,
                source_name=n.source_name,
                source_url=n.source_url,
                published_at=n.published_at,
                image_url=n.image_url,
                has_card_summary=n.card_summary is not None,
            )
            for n in rows
        ]

    async def get_detail(self, session: AsyncSession, news_id: int) -> HealthNewsDetailResponse | None:
        """상세화면. 카드요약을 함께 실어 보내므로 [카드요약보기]에 추가 요청이 없다
        (TRD T-LLM-4의 "별도 대기 없이")."""
        news = await self._repo.get_by_id(session, news_id)
        if news is None:
            return None
        return HealthNewsDetailResponse(
            id=news.id,
            title=news.title,
            source_name=news.source_name,
            source_url=news.source_url,
            published_at=news.published_at,
            body_text=news.body_text,
            image_url=news.image_url,
            image_caption=news.image_caption,
            card_summary=self._parse_card_summary(news),
            # 면책 문구는 DB에 저장하지 않고 응답 시점에 붙인다 - 문구가 바뀌면 기존 기사까지
            # 한 번에 반영돼야 하기 때문(REQ-INFO-004).
            disclaimer=DISCLAIMER_TEXT,
        )

    @staticmethod
    def _parse_card_summary(news: HealthNews) -> CardSummary | None:
        """저장된 JSON을 스키마로 되돌린다. 옛 스키마로 저장된 행이 섞여 있어도 상세화면 전체가
        500이 되지 않게, 검증 실패는 "요약 없음"으로 떨어뜨린다(재생성 대상이 된다)."""
        if news.card_summary is None:
            return None
        try:
            return CardSummary.model_validate(news.card_summary)
        except ValueError:
            logger.warning("저장된 카드요약이 현재 스키마와 맞지 않습니다 (news_id=%s)", news.id)
            return None
