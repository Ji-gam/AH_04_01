from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import Notice, NoticeKind


class NoticeRepository:
    async def list_all(self, session: AsyncSession) -> list[Notice]:
        result = await session.execute(select(Notice).order_by(Notice.created_at.asc()))
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, kind: NoticeKind, title: str, body: str) -> Notice:
        notice = Notice(kind=kind, title=title, body=body)
        session.add(notice)
        await session.commit()
        # created_at은 server_default(DB가 계산)라 커밋만으로는 파이썬 객체에 값이 안
        # 채워진다 - 나중에(라우터에서) 동기적으로 접근하면 그때 지연로딩을 시도하다
        # MissingGreenlet 에러가 난다. 여기서 미리 채워서 반환한다.
        await session.refresh(notice)
        return notice
