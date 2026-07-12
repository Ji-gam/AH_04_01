from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import HealthContent


class ContentRepository:
    async def get_by_disease_category_date(
        self, session: AsyncSession, disease_code: str, category: str, content_date: date
    ) -> HealthContent | None:
        result = await session.execute(
            select(HealthContent).where(
                HealthContent.disease_code == disease_code,
                HealthContent.category == category,
                HealthContent.content_date == content_date,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, session: AsyncSession, **fields) -> HealthContent:
        content = HealthContent(**fields)
        session.add(content)
        await session.commit()
        await session.refresh(content)
        return content

    async def update_card(
        self,
        session: AsyncSession,
        content: HealthContent,
        *,
        title: str,
        summary: str,
        body: str,
        image_prompt: str | None,
    ) -> HealthContent:
        """카드 본문만 갱신한다(질환/카테고리/날짜는 유니크 제약 키라 안 바꾼다) —
        수동 재생성 시 새 행을 만드는 대신 같은 (질환, 카테고리, 날짜) 캐시를 덮어쓴다."""
        content.title = title
        content.summary = summary
        content.body = body
        content.image_prompt = image_prompt
        await session.commit()
        await session.refresh(content)
        return content

    async def list_by_diseases(
        self,
        session: AsyncSession,
        disease_codes: list[str] | None,
        category: str | None,
        limit: int | None = None,
    ) -> list[HealthContent]:
        """누적 피드 조회. `disease_codes`가 None이면 질환 필터 없이 전체를 반환한다
        (비로그인/질환 미등록 사용자의 "전체 콘텐츠" 폴백)."""
        query = select(HealthContent)
        if disease_codes is not None:
            query = query.where(HealthContent.disease_code.in_(disease_codes))
        if category is not None:
            query = query.where(HealthContent.category == category)
        query = query.order_by(HealthContent.content_date.desc(), HealthContent.id.desc())
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())
