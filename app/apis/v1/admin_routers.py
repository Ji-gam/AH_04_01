from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_admin_user
from app.dtos.admin import (
    AdminActionResponse,
    AdminNoticeResponse,
    AdminStatsResponse,
    AdminUserResponse,
    ErrorLogResponse,
    NoticeUpdateRequest,
    OpsStatsResponse,
    SetAdminRequest,
)
from app.dtos.health_news_dto import (
    AdminHealthNewsResponse,
    CardSummaryBatchResponse,
    CollectNewsResponse,
    HealthNewsUpdateRequest,
)
from app.models.users import User
from app.services.admin_service import AdminService
from app.services.ai_worker_gateway import AIWorkerUnavailableError

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/stats",
    response_model=AdminStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="관리자 대시보드 통계 조회 (관리자 전용)",
    description="전체 가입자/관리자 수, 가입자 추이(기간 지정 가능), 항목별 동의자 수, 최근 24시간 오류 건수를 한 번에 조회.",
)
async def get_stats(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90, description="가입자 추이 조회 기간(일). 기본 7일, 최대 90일."),
) -> AdminStatsResponse:
    service = AdminService()
    stats = await service.get_stats(session, days=days)
    return AdminStatsResponse(**stats)


@admin_router.get(
    "/ops-stats",
    response_model=OpsStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="관리자 대시보드 운영 현황 조회 (관리자 전용)",
    description=(
        "DAU/WAU, 근사 복약 순응도, 상위 약품(소수 인원 그룹 제외), 콘텐츠/챗봇/알림/가족연결/"
        "탈퇴 추이, AI-worker 상태를 한 번에 조회한다. 전부 익명 집계."
    ),
)
async def get_ops_stats(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OpsStatsResponse:
    service = AdminService()
    stats = await service.get_ops_stats(session)
    return OpsStatsResponse(**stats)


@admin_router.get(
    "/notices",
    response_model=list[AdminNoticeResponse],
    status_code=status.HTTP_200_OK,
    summary="공지 목록 조회 (관리자 전용)",
)
async def list_notices_admin(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminNoticeResponse]:
    service = AdminService()
    notices = await service.list_notices_admin(session)
    return [AdminNoticeResponse.model_validate(n) for n in notices]


@admin_router.patch(
    "/notices/{notice_id}",
    response_model=AdminNoticeResponse,
    status_code=status.HTTP_200_OK,
    summary="공지 수정 (관리자 전용)",
    description="보낸 필드만 갱신한다. 수정만 하고 재발송은 하지 않는다(이미 받은 사람에게 중복 알림 방지).",
)
async def update_notice_admin(
    notice_id: int,
    body: NoticeUpdateRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminNoticeResponse:
    service = AdminService()
    updated = await service.update_notice(session, admin, notice_id, body)
    return AdminNoticeResponse.model_validate(updated)


@admin_router.delete(
    "/notices/{notice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="공지 삭제 (관리자 전용)",
)
async def delete_notice_admin(
    notice_id: int,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = AdminService()
    await service.delete_notice(session, admin, notice_id)


@admin_router.post(
    "/news/collect",
    response_model=CollectNewsResponse,
    status_code=status.HTTP_200_OK,
    summary="건강 뉴스 수집 실행 (관리자 전용)",
    description=(
        "T-LLM-6: 등록된 모든 매체(코메디닷컴·헬스경향·코리아헬스로그)를 1회 수집한다. "
        "주기 자동 수집(Celery worker/beat)이 붙기 전까지 이 버튼이 유일한 트리거다.\n\n"
        "**카드요약은 여기서 만들지 않는다**(2026-07-31 변경). 요약은 기사 1건당 4~5초라 수집과 "
        "한 요청에 묶으면 게이트웨이 타임아웃(504)을 맞는다 - 실제로 겪었다. 수집 자체는 3.3초로 "
        "끝나고, 요약은 `POST /news/card-summaries/fill`을 `remaining`이 0이 될 때까지 여러 번 "
        "불러 채운다. 아직 요약이 없는 기사 수는 `pending_summaries`로 돌려준다.\n\n"
        "여러 번 눌러도 안전하다 - 이미 저장된 기사는 건너뛴다. "
        "매체당 최신 몇 건까지만 가져오며(카드요약 LLM 비용 상한), 상한을 넘어 미룬 수는 `over_limit`로 "
        "돌려준다. 공시·제약사 카테고리 기사는 건강정보가 아니라 저장하지 않으며 그 수는 `excluded`다. "
        "매체 하나가 실패해도 나머지는 계속 수집하고, 실패 원인은 `collect_error`에 담긴다. "
        "admin_actions에 감사로그로 남는다."
    ),
)
async def collect_health_news_admin(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CollectNewsResponse:
    service = AdminService()
    collected, pending_summaries = await service.collect_health_news(session, admin)
    return CollectNewsResponse(
        fetched=collected.fetched,
        excluded=collected.excluded,
        created=collected.created,
        skipped=collected.skipped,
        over_limit=collected.over_limit,
        unreadable=collected.unreadable,
        collect_error=collected.first_error,
        pending_summaries=pending_summaries,
    )


@admin_router.post(
    "/news/card-summaries/fill",
    response_model=CardSummaryBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="카드요약 없는 기사 채우기 (한 배치, 관리자 전용)",
    description=(
        "카드요약이 아직 없는 기사의 요약을 **한 배치만** 만든다. 한 번에 처리할 건수는 서버가 "
        "정한다(`CARD_SUMMARY_BATCH_SIZE`) - 클라이언트가 크게 요청해서 타임아웃을 자초할 수 "
        "없어야 한다.\n\n"
        "전부 채우려면 응답의 `remaining`이 0이 될 때까지 반복 호출한다. **`generated`가 0인데 "
        "`remaining`이 남아 있으면 멈춰야 한다** - 같은 기사가 계속 실패하는 상황이라 이어 불러도 "
        "무한 반복된다. 그때는 `error`에 원인이 담겨 있다.\n\n"
        "기사 한 건이 실패해도 나머지는 계속 처리하고, 실패한 기사는 요약이 빈 채로 남아 다음 "
        "배치에서 자동으로 다시 시도된다. LLM 호출 비용이 드는 행위라서 배치마다 감사로그로 남는다."
    ),
    responses={503: {"description": "ai_worker가 응답하지 않아 카드요약을 만들 수 없음."}},
)
async def fill_card_summaries_admin(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CardSummaryBatchResponse:
    service = AdminService()
    try:
        summarized = await service.fill_card_summaries(session, admin)
    except AIWorkerUnavailableError as e:
        # 기사 단위로 예외를 삼키므로 여기까지 오는 건 게이트웨이 구성 문제일 때다.
        raise HTTPException(status_code=503, detail=f"카드요약 생성을 할 수 없습니다: {e}") from e
    return CardSummaryBatchResponse(
        attempted=summarized.pending,
        generated=summarized.generated,
        failed=summarized.failed,
        remaining=summarized.remaining,
        # fill은 "요약이 빈 기사"만 고르므로 진행 위치를 들고 다닐 필요가 없다.
        next_offset=0,
        error=summarized.first_error,
    )


@admin_router.post(
    "/news/card-summaries/regenerate",
    response_model=CardSummaryBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="카드요약 다시 만들기 (한 배치, 관리자 전용)",
    description=(
        "저장된 기사의 카드요약을 다시 만든다. 평소 수집 배치는 요약이 비어 있는 기사만 "
        "고르기 때문에, 프롬프트나 글자 수 제한을 손질해도 이미 요약이 있는 기사는 옛 기준으로 "
        "남는다. 그때 쓰는 버튼이다.\n\n"
        "**한 배치만 처리한다**(`fill`과 같은 이유 - 게이트웨이 타임아웃). 전체를 다시 만들려면 "
        "응답의 `next_offset`을 다음 요청의 `offset`으로 넘기며 `remaining`이 0이 될 때까지 "
        "반복한다. 요약이 이미 있는 기사도 대상이라 진행 위치가 데이터에 남지 않기 때문에 "
        "`fill`과 달리 offset이 필요하다.\n\n"
        "기존 요약을 먼저 지우지 않는다 - 새로 만들기에 성공한 것만 덮어쓰므로, LLM이 실패해도 "
        "쓸 만했던 요약을 잃지 않는다.\n\n"
        "기사 수만큼 LLM을 부르는 비싼 행위라서 배치마다 감사로그로 남는다."
    ),
    responses={503: {"description": "ai_worker가 응답하지 않아 카드요약을 만들 수 없음."}},
)
async def regenerate_card_summaries_admin(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    offset: Annotated[int, Query(ge=0, description="다시 만들기를 이어갈 위치. 첫 호출은 0.")] = 0,
) -> CardSummaryBatchResponse:
    service = AdminService()
    try:
        summarized = await service.regenerate_card_summaries(session, admin, offset=offset)
    except AIWorkerUnavailableError as e:
        # 기사 단위로 예외를 삼키므로 여기까지 오는 건 게이트웨이 구성 문제일 때다.
        raise HTTPException(status_code=503, detail=f"카드요약 생성을 할 수 없습니다: {e}") from e
    return CardSummaryBatchResponse(
        attempted=summarized.pending,
        generated=summarized.generated,
        failed=summarized.failed,
        remaining=summarized.remaining,
        # 실패한 기사도 지나간 것으로 센다 - 여기서 멈춰 서면 같은 기사를 영원히 다시 시도한다.
        next_offset=offset + summarized.pending,
        error=summarized.first_error,
    )


@admin_router.get(
    "/news",
    response_model=list[AdminHealthNewsResponse],
    status_code=status.HTTP_200_OK,
    summary="수집된 건강 뉴스 목록 조회 (관리자 전용)",
    description="발행일 최신순. `source_categories`를 함께 보여줘서 수집 필터 기준을 조정할 근거로 쓴다.",
)
async def list_health_news_admin(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AdminHealthNewsResponse]:
    service = AdminService()
    rows = await service.list_health_news_admin(session, limit=limit)
    return [
        AdminHealthNewsResponse(
            id=n.id,
            source=n.source,
            source_name=n.source_name,
            source_url=n.source_url,
            title=n.title,
            published_at=n.published_at,
            image_url=n.image_url,
            source_categories=n.source_categories,
            disease_code=n.disease_code,
            has_card_summary=n.card_summary is not None,
            fetched_at=n.fetched_at,
        )
        for n in rows
    ]


@admin_router.patch(
    "/news/{news_id}",
    response_model=AdminHealthNewsResponse,
    status_code=status.HTTP_200_OK,
    summary="건강 뉴스 수정 (관리자 전용)",
    description="보낸 필드만 갱신한다. source/source_url은 중복 판단 키라 여기서 안 바꾼다.",
    responses={404: {"description": "해당 id의 기사가 없음"}},
)
async def update_health_news_admin(
    news_id: int,
    body: HealthNewsUpdateRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminHealthNewsResponse:
    service = AdminService()
    n = await service.update_health_news(session, admin, news_id, body)
    return AdminHealthNewsResponse(
        id=n.id,
        source=n.source,
        source_name=n.source_name,
        source_url=n.source_url,
        title=n.title,
        published_at=n.published_at,
        image_url=n.image_url,
        source_categories=n.source_categories,
        disease_code=n.disease_code,
        has_card_summary=n.card_summary is not None,
        fetched_at=n.fetched_at,
    )


@admin_router.delete(
    "/news/{news_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="건강 뉴스 삭제 (관리자 전용)",
    description=(
        "AI 요약이 기사를 왜곡했거나 건강정보로 부적절한 기사를 내리는 경로. "
        "'관리자 승인 후 노출' 게이트를 두지 않기로 했으므로 이게 유일한 교정 수단이다."
    ),
    responses={404: {"description": "해당 id의 기사가 없음"}},
)
async def delete_health_news_admin(
    news_id: int,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = AdminService()
    await service.delete_health_news(session, admin, news_id)


@admin_router.get(
    "/error-logs",
    response_model=list[ErrorLogResponse],
    status_code=status.HTTP_200_OK,
    summary="서버 오류 로그 조회 (관리자 전용, AI챗봇 제외)",
    description=(
        "챗봇 이외의 API에서 발생한 미처리 예외를 최신순 100건까지 조회한다. "
        "전체 트레이스백/요청 바디는 저장하지 않으며, 예외 타입 + 200자로 잘라낸 메시지만 남는다."
    ),
)
async def list_error_logs(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ErrorLogResponse]:
    service = AdminService()
    logs = await service.list_error_logs(session)
    return [ErrorLogResponse.model_validate(e) for e in logs]


@admin_router.get(
    "/users",
    response_model=list[AdminUserResponse],
    status_code=status.HTTP_200_OK,
    summary="사용자 목록 조회 (관리자 전용)",
    description="이메일 부분일치 검색 가능. 관리자 승격 대상을 찾는 용도라 최신 가입순 50건으로 제한.",
)
async def list_users(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None, description="이메일 부분일치 검색"),
) -> list[AdminUserResponse]:
    # (2026-07-27) Depends(AdminService)로 썼다가 서버 자체가 부팅 실패했던 문제 수정 -
    # AdminService.__init__이 UserRepository 같은 Pydantic 아닌 타입 인자를 받아서,
    # FastAPI가 그걸 쿼리 파라미터로 잘못 해석함. 다른 서비스들(MedicationService 등)과
    # 동일하게 함수 안에서 직접 생성하는 방식으로 통일.
    service = AdminService()
    users = await service.list_users(session, search)
    return [AdminUserResponse.model_validate(u) for u in users]


@admin_router.patch(
    "/users/{user_id}/admin",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="관리자 권한 승격/해제 (관리자 전용)",
    description=(
        "지정한 사용자의 is_admin을 켜거나 끈다. 이 행위는 admin_actions에 감사로그로 남는다. "
        "새 공개 가입 경로(초대코드 등)를 만드는 대신, 이미 있는 관리자가 승격시키는 방식만 지원한다 - "
        "최초 관리자 1명은 서버에서 app/scripts/promote_admin.py로 지정한다."
    ),
)
async def set_admin(
    user_id: int,
    body: SetAdminRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    service = AdminService()
    target = await service.set_admin(session, admin, user_id, body.is_admin)
    return AdminUserResponse.model_validate(target)


@admin_router.get(
    "/actions",
    response_model=list[AdminActionResponse],
    status_code=status.HTTP_200_OK,
    summary="관리자 행위 감사로그 조회 (관리자 전용)",
    description="권한 승격/해제, 공지 발송 등 관리자 화면에서 이뤄진 행위를 최신순 100건까지 조회.",
)
async def list_actions(
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminActionResponse]:
    service = AdminService()
    actions = await service.list_actions(session)
    return [AdminActionResponse.model_validate(a) for a in actions]
