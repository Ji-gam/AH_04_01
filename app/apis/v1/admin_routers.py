from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_admin_user
from app.dtos.admin import (
    AdminActionResponse,
    AdminStatsResponse,
    AdminUserResponse,
    ErrorLogResponse,
    OpsStatsResponse,
    SetAdminRequest,
)
from app.models.users import User
from app.services.admin_service import AdminService

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
