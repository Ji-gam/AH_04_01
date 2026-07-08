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

    async def list_by_diseases(
        self, session: AsyncSession, disease_codes: list[str] | None, category: str | None
    ) -> list[HealthContent]:
        """누적 피드 조회. `disease_codes`가 None이면 질환 필터 없이 전체를 반환한다
        (비로그인/질환 미등록 사용자의 "전체 콘텐츠" 폴백)."""
        query = select(HealthContent)
        if disease_codes is not None:
            query = query.where(HealthContent.disease_code.in_(disease_codes))
        if category is not None:
            query = query.where(HealthContent.category == category)
        query = query.order_by(HealthContent.content_date.desc(), HealthContent.id.desc())
        result = await session.execute(query)
        return list(result.scalars().all())
