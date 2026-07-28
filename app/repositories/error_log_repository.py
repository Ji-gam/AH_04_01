from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_log import ErrorLog


class ErrorLogRepository:
    async def log(
        self,
        session: AsyncSession,
        *,
        method: str,
        path: str,
        exception_type: str,
        message: str | None,
        status_code: int,
    ) -> ErrorLog:
        record = ErrorLog(
            method=method,
            path=path,
            exception_type=exception_type,
            message=message[:200] if message else None,
            status_code=status_code,
        )
        session.add(record)
        await session.commit()
        return record

    async def list_recent(self, session: AsyncSession, limit: int = 100) -> list[ErrorLog]:
        stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_since(self, session: AsyncSession, since) -> int:  # noqa: ANN001
        from sqlalchemy import func

        stmt = select(func.count()).select_from(ErrorLog).where(ErrorLog.created_at >= since)
        result = await session.execute(stmt)
        return result.scalar_one()
