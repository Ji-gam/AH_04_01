"""T-LLM-6 건강 뉴스 피드 API.

기존 `/contents/*`(T-LLM-3)를 대체한다. 두 경로는 6단계에서 프론트가 이쪽으로 옮겨온 뒤
`/contents/*`를 제거할 때까지만 잠시 공존한다.

`/contents/me`처럼 로그인 없이도 조회 가능한 공개 엔드포인트로 둔다 - 건강 뉴스는 사용자별
데이터가 아니고, 개인화(2단계)가 붙기 전까지는 누가 봐도 같은 결과다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dtos.health_news_dto import HealthNewsDetailResponse, HealthNewsFeedResponse
from app.services.health_news_service import HealthNewsService

health_news_router = APIRouter(prefix="/news", tags=["HealthNews"])


@health_news_router.get(
    "",
    response_model=HealthNewsFeedResponse,
    summary="건강 뉴스 피드 조회",
    description=(
        "건강정보 화면의 뉴스 피드. 로그인 없이 조회 가능하다. 발행일 최신순으로 반환한다 "
        "(개인화 정렬은 2단계). 목록에는 본문을 담지 않는다 - 기사마다 1~3KB씩이라 목록 응답만 "
        "무거워지기 때문이며, 본문은 단건 조회에서 받는다. "
        "`has_card_summary`가 false인 기사는 [카드요약보기]를 비활성으로 두면 된다."
    ),
)
async def get_health_news_feed(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int | None, Query(ge=1, le=100, description="반환 개수(미지정 시 서버 기본값)")] = None,
) -> HealthNewsFeedResponse:
    items = await HealthNewsService().get_feed(session, limit=limit)
    return HealthNewsFeedResponse(items=items)


@health_news_router.get(
    "/{news_id}",
    response_model=HealthNewsDetailResponse,
    summary="건강 뉴스 단건 조회",
    description=(
        "상세화면 진입/새로고침용. 라우터 state가 아니라 항상 DB에서 다시 조회하므로 직접 URL "
        "접근에도 동작한다. 카드요약(`card_summary`)이 이 응답에 함께 실려 오므로 "
        "[카드요약보기]를 눌러도 추가 요청 없이 즉시 열린다. `card_summary`가 null이면 아직 "
        "생성 전이다. 면책 문구(`disclaimer`)는 응답 시점에 붙는다."
    ),
    responses={404: {"description": "해당 id의 기사가 없음"}},
)
async def get_health_news_detail(
    news_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthNewsDetailResponse:
    detail = await HealthNewsService().get_detail(session, news_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다.")
    return detail
