from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.notice import NoticeCreateRequest, NoticeResponse
from app.models.notice import Notice
from app.models.profiles import Profile
from app.services.notice_service import NoticeService

notice_router = APIRouter(prefix="/notices", tags=["notices"])


def _to_response(notice: Notice, *, is_new: bool) -> NoticeResponse:
    return NoticeResponse(
        id=notice.id,
        kind=notice.kind.value,
        title=notice.title,
        body=notice.body,
        created_at=notice.created_at,
        is_new=is_new,
    )


@notice_router.get(
    "",
    response_model=list[NoticeResponse],
    status_code=status.HTTP_200_OK,
    summary="공지사항 목록 조회",
    description="등록된 공지/마케팅 소식을 등록 순서(오래된 순)로 반환한다. 가장 최근 항목만 is_new=true.",
)
async def list_notices(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NoticeService, Depends(NoticeService)],
) -> list[NoticeResponse]:
    notices = await service.list_notices(session)
    return [_to_response(n, is_new=(i == len(notices) - 1)) for i, n in enumerate(notices)]


@notice_router.post(
    "",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공지사항 등록",
    description=(
        "새 공지/마케팅 소식을 등록하고, kind에 맞는 알림설정(공지사항 알림/마케팅 알림)을 "
        "켜둔 프로필 전체에 푸시를 보낸다."
    ),
)
async def create_notice(
    data: NoticeCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NoticeService, Depends(NoticeService)],
) -> NoticeResponse:
    notice = await service.create_notice(session, data)
    return _to_response(notice, is_new=True)
