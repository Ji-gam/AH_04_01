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
