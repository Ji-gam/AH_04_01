from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile, get_request_user
from app.dtos.health_info import DiagnosisEntry, FamilyHistoryEntry, HealthInfoResponse, HealthInfoUpdateRequest
from app.dtos.users import UserInfoResponse, UserUpdateRequest
from app.models.disease_entries import DiagnosisEntry as DiagnosisEntryModel
from app.models.disease_entries import FamilyHistoryEntry as FamilyHistoryEntryModel
from app.models.profiles import Profile
from app.models.users import User
from app.repositories.disease_entry_repository import DiagnosisEntryRepository, FamilyHistoryEntryRepository
from app.services.age_calculator import resolve_display_age
from app.services.health_info import HealthInfoService
from app.services.users import UserManageService

user_router = APIRouter(prefix="/users", tags=["users"])


def _to_user_info_response(user: User, profile: Profile) -> UserInfoResponse:
    return UserInfoResponse(
        id=user.id,
        profile_id=profile.id,
        name=profile.name,
        email=user.email,
        phone_number=profile.phone_number,
        gender=profile.gender,
        created_at=user.created_at,
    )


def _to_diagnosis_dto(row: DiagnosisEntryModel) -> DiagnosisEntry:
    return DiagnosisEntry(
        disease=row.disease,
        disease_subtype=row.disease_subtype.name if row.disease_subtype else None,
        diagnosed_years_ago=row.diagnosed_years_ago,
        status=row.status,
        on_medication=row.on_medication,
        detail=row.detail,
    )


def _to_family_history_dto(row: FamilyHistoryEntryModel) -> FamilyHistoryEntry:
    return FamilyHistoryEntry(
        disease=row.disease,
        disease_subtype=row.disease_subtype.name if row.disease_subtype else None,
        relation=row.relation,
        detail=row.detail,
    )


async def _to_health_info_response(
    session: AsyncSession,
    profile: Profile,
    diagnosis_repo: DiagnosisEntryRepository,
    family_repo: FamilyHistoryEntryRepository,
) -> HealthInfoResponse:
    diagnosis_rows = await diagnosis_repo.list_for_profile(session, profile.id)
    family_rows = await family_repo.list_for_profile(session, profile.id)
    return HealthInfoResponse(
        age=resolve_display_age(profile.birth_date),
        birth_date=profile.birth_date,
        gender=profile.gender,
        height_cm=float(profile.height_cm) if profile.height_cm is not None else None,
        weight_kg=float(profile.weight_kg) if profile.weight_kg is not None else None,
        diagnosis_history=[_to_diagnosis_dto(r) for r in diagnosis_rows],
        family_history=[_to_family_history_dto(r) for r in family_rows],
        special_notes=profile.special_notes,
        other_notes=profile.other_notes,
    )


@user_router.get(
    "/me",
    response_model=UserInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="내 정보 조회",
    description="Authorization: Bearer 토큰의 user_id/profile_id로 User(계정)와 본인 Profile을 합쳐서 반환한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def user_me_info(
    user: Annotated[User, Depends(get_request_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> Response:
    return Response(_to_user_info_response(user, profile).model_dump(), status_code=status.HTTP_200_OK)


@user_router.patch(
    "/me",
    response_model=UserInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="내 정보 수정",
    description=(
        "전달한 필드(name/phone_number/gender)만 부분 수정해서 Profile에 반영하고, "
        "User와 합친 최신 정보를 반환한다. email은 로그인 식별자라 여기서 수정할 수 없다(가입 후 고정)."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_409_CONFLICT: {"description": "변경하려는 휴대폰 번호가 이미 사용 중"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "휴대폰번호 형식이 유효하지 않음"},
    },
)
async def update_user_me_info(
    update_data: UserUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    updated_user, updated_profile = await user_manage_service.update_user(session, user, profile, update_data)
    return Response(_to_user_info_response(updated_user, updated_profile).model_dump(), status_code=status.HTTP_200_OK)


@user_router.get(
    "/me/health-info",
    response_model=HealthInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="개인건강정보 조회",
    description=(
        "나이/성별/키/체중/진단병력/가족력/특이사항/기타를 조회한다. "
        "키·체중이 둘 다 있으면 bmi를 계산해서 같이 내려준다(하나라도 없으면 null)."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_health_info(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    diagnosis_repo: Annotated[DiagnosisEntryRepository, Depends(DiagnosisEntryRepository)],
    family_repo: Annotated[FamilyHistoryEntryRepository, Depends(FamilyHistoryEntryRepository)],
) -> Response:
    response = await _to_health_info_response(session, profile, diagnosis_repo, family_repo)
    return Response(response.model_dump(), status_code=status.HTTP_200_OK)


@user_router.patch(
    "/me/health-info",
    response_model=HealthInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="개인건강정보 수정",
    description=(
        "전달한 필드만 부분 수정한다. 전부 선택 입력이며 회원가입 흐름과 무관하게 언제든 호출할 수 있다. "
        "가입 시 나이/성별을 안 받으므로, 여기서 처음 입력받는 경우가 일반적이다. "
        "diagnosis_history/family_history에 빈 리스트를 보내면 전부 지워진다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "키/체중 범위가 유효하지 않음"},
    },
)
async def update_health_info(
    update_data: HealthInfoUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    health_info_service: Annotated[HealthInfoService, Depends(HealthInfoService)],
    diagnosis_repo: Annotated[DiagnosisEntryRepository, Depends(DiagnosisEntryRepository)],
    family_repo: Annotated[FamilyHistoryEntryRepository, Depends(FamilyHistoryEntryRepository)],
) -> Response:
    updated_profile = await health_info_service.update_health_info(session, profile, update_data)
    response = await _to_health_info_response(session, updated_profile, diagnosis_repo, family_repo)
    return Response(response.model_dump(), status_code=status.HTTP_200_OK)
