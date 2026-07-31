from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notice import Notice, NoticeKind


class NoticeRepository:
    async def list_all(self, session: AsyncSession) -> list[Notice]:
        result = await session.execute(select(Notice).order_by(Notice.created_at.asc()))
        return list(result.scalars().all())

    async def get_by_id(self, session: AsyncSession, notice_id: int) -> Notice | None:
        return await session.get(Notice, notice_id)

    async def create(self, session: AsyncSession, kind: NoticeKind, title: str, body: str) -> Notice:
        notice = Notice(kind=kind, title=title, body=body)
        session.add(notice)
        await session.commit()
        # created_at은 server_default(DB가 계산)라 커밋만으로는 파이썬 객체에 값이 안
        # 채워진다 - 나중에(라우터에서) 동기적으로 접근하면 그때 지연로딩을 시도하다
        # MissingGreenlet 에러가 난다. 여기서 미리 채워서 반환한다.
        await session.refresh(notice)
        return notice

    async def update(
        self,
        session: AsyncSession,
        notice: Notice,
        *,
        kind: NoticeKind | None,
        title: str | None,
        body: str | None,
    ) -> Notice:
        """(관리자 화면) 등록한 공지의 오탈자/내용 수정용 - 재발송은 하지 않는다(수정
        시점에 다시 알림을 쏘면 이미 받은 사람에게 중복 발송되므로 별개로 취급)."""
        if kind is not None:
            notice.kind = kind
        if title is not None:
            notice.title = title
        if body is not None:
            notice.body = body
        await session.commit()
        await session.refresh(notice)
        return notice

    async def delete(self, session: AsyncSession, notice: Notice) -> None:
        await session.delete(notice)
        await session.commit()
