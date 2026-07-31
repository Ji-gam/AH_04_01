from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_news import HealthNews


class HealthNewsRepository:
    """T-LLM-6 수집 기사 저장소. 수집 배치와 조회 API가 같이 쓴다."""

    async def get_by_source_url(self, session: AsyncSession, source: str, source_url: str) -> HealthNews | None:
        result = await session.execute(
            select(HealthNews).where(HealthNews.source == source, HealthNews.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def save(self, session: AsyncSession, **fields: Any) -> HealthNews:
        news = HealthNews(**fields)
        session.add(news)
        await session.commit()
        await session.refresh(news)
        return news

    async def list_feed(self, session: AsyncSession, limit: int | None = None) -> list[HealthNews]:
        """뉴스 피드 조회. 1단계는 개인화 없이 발행일 최신순 전체다(질환 태깅은 2단계).
        발행일이 같은 기사끼리는 id 역순으로 안정적인 순서를 보장한다."""
        query = select(HealthNews).order_by(HealthNews.published_at.desc(), HealthNews.id.desc())
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, session: AsyncSession, news_id: int) -> HealthNews | None:
        """상세화면 단건 조회. 직접 URL 접근/새로고침에도 동작해야 하므로 항상 DB에서 다시 조회한다."""
        result = await session.execute(select(HealthNews).where(HealthNews.id == news_id))
        return result.scalar_one_or_none()

    async def list_missing_card_summary(self, session: AsyncSession, limit: int | None = None) -> list[HealthNews]:
        """카드요약이 아직 없는 기사들. 수집 배치가 요약 생성 대상을 고를 때 쓴다 -
        LLM 호출이 중간에 실패해도 다음 실행이 빠진 것만 다시 채운다."""
        query = select(HealthNews).where(HealthNews.card_summary.is_(None)).order_by(HealthNews.published_at.desc())
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def set_card_summary(
        self, session: AsyncSession, news: HealthNews, card_summary: dict[str, Any]
    ) -> HealthNews:
        news.card_summary = card_summary
        await session.commit()
        await session.refresh(news)
        return news

    async def update_article(
        self,
        session: AsyncSession,
        news: HealthNews,
        *,
        title: str,
        body_text: str,
    ) -> HealthNews:
        """(관리자 화면) 제목/본문만 손본다 - source/source_url은 유니크 제약 키이므로 건드리지 않는다."""
        news.title = title
        news.body_text = body_text
        await session.commit()
        await session.refresh(news)
        return news

    async def delete(self, session: AsyncSession, news: HealthNews) -> None:
        """(관리자 화면) 건강 정보로 부적절한 기사가 섞여 들어왔을 때 내리는 용도."""
        await session.delete(news)
        await session.commit()
