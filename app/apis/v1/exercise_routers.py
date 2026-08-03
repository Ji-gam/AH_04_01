from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.exercise_dto import (
    ExerciseLogCreateRequest,
    ExerciseMetEstimateRequest,
    ExerciseMetEstimateResult,
    ExerciseRecentResult,
    ExerciseSearchResult,
    ExerciseTodayResult,
)
from app.models.profiles import Profile
from app.services.exercise_service import ExerciseService

exercise_router = APIRouter(prefix="/exercise", tags=["exercise"])


@exercise_router.get(
    "/catalog",
    response_model=ExerciseSearchResult,
    status_code=status.HTTP_200_OK,
    summary="운동 종류 전체 목록 조회 (드롭다운용)",
    description=(
        "더보기 > 마이다이어리 > 운동 기록 화면의 드롭다운용. 웨이트/근력운동처럼 세부 종목별 "
        "입력은 지원하지 않는 고정된 23개 운동 목록을 그대로 반환한다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_exercise_catalog(
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> ExerciseSearchResult:
    service = ExerciseService()
    return await service.list_catalog()


@exercise_router.get(
    "/search",
    response_model=ExerciseSearchResult,
    status_code=status.HTTP_200_OK,
    summary="운동 이름으로 MET 값 검색",
    description="더보기 > 마이다이어리 > 운동 기록 화면의 검색창용. 검색어와 부분 일치하는 운동을 MET(대사당량) 값과 함께 반환한다.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "검색어가 비어 있음"},
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
    },
)
async def search_exercise(
    query: str,
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> ExerciseSearchResult:
    service = ExerciseService()
    return await service.search_exercise(query)


@exercise_router.post(
    "/estimate-met",
    response_model=ExerciseMetEstimateResult,
    status_code=status.HTTP_200_OK,
    summary="목록에 없는 운동의 MET 값을 AI로 추정",
    description=(
        "드롭다운의 '기타(직접 입력)' 선택 후 자유 입력한 운동명을 AI로 인식해 MET(대사당량) "
        "값을 추정한다. 이후 이 값을 그대로 POST /exercise/logs의 input_mode=duration으로 기록한다. "
        "AI 호출이 실패해도 항상 폴백 값으로 200을 반환한다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def estimate_exercise_met(
    body: ExerciseMetEstimateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> ExerciseMetEstimateResult:
    service = ExerciseService()
    return await service.estimate_met(body.exercise_name)


@exercise_router.post(
    "/logs",
    response_model=ExerciseTodayResult,
    status_code=status.HTTP_201_CREATED,
    summary="운동 기록 추가",
    description="검색 결과(운동명 + MET 값)와 운동 시간(분)을 보내면 소모 칼로리를 계산해 오늘 기록으로 저장한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def log_exercise(
    body: ExerciseLogCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseTodayResult:
    service = ExerciseService()
    return await service.log_exercise(session, profile, body)


@exercise_router.get(
    "/today",
    response_model=ExerciseTodayResult,
    status_code=status.HTTP_200_OK,
    summary="오늘 운동 기록 및 총 소모 칼로리 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_today(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseTodayResult:
    service = ExerciseService()
    return await service.get_today(session, profile)


@exercise_router.delete(
    "/logs/{log_id}",
    response_model=ExerciseTodayResult,
    status_code=status.HTTP_200_OK,
    summary="운동 기록 삭제",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 기록"},
    },
)
async def delete_log(
    log_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseTodayResult:
    service = ExerciseService()
    return await service.delete_log(session, profile, log_id)


@exercise_router.get(
    "/recent",
    response_model=ExerciseRecentResult,
    status_code=status.HTTP_200_OK,
    summary="최근 7일(오늘 포함) 일별 총 소모 칼로리 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_recent(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseRecentResult:
    service = ExerciseService()
    return await service.get_recent(session, profile)
