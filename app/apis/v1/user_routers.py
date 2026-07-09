from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile, get_request_user
from app.dtos.health_info import HealthInfoResponse, HealthInfoUpdateRequest
from app.dtos.users import UserInfoResponse, UserUpdateRequest
from app.models.profiles import Disease, Profile
from app.models.users import User
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
        birthday=profile.birthday,
        gender=profile.gender,
        created_at=user.created_at,
    )


def _to_health_info_response(profile: Profile) -> HealthInfoResponse:
    return HealthInfoResponse(
        birthday=profile.birthday,
        gender=profile.gender,
        height_cm=float(profile.height_cm) if profile.height_cm is not None else None,
        weight_kg=float(profile.weight_kg) if profile.weight_kg is not None else None,
        diagnosis_history=[Disease(d) for d in (profile.diagnosis_history or [])],
        family_history=[Disease(d) for d in (profile.family_history or [])],
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
        "전달한 필드(name/phone_number/birthday/gender)만 부분 수정해서 Profile에 반영하고, "
        "User와 합친 최신 정보를 반환한다. email은 로그인 식별자라 여기서 수정할 수 없다(가입 후 고정)."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_409_CONFLICT: {"description": "변경하려는 휴대폰 번호가 이미 사용 중"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "생년월일/휴대폰번호 형식이 유효하지 않음"},
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
        "생년월일/성별/키/체중/진단병력/가족력/특이사항/기타를 조회한다. "
        "키·체중이 둘 다 있으면 bmi를 계산해서 같이 내려준다(하나라도 없으면 null)."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_health_info(
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> Response:
    return Response(_to_health_info_response(profile).model_dump(), status_code=status.HTTP_200_OK)


@user_router.patch(
    "/me/health-info",
    response_model=HealthInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="개인건강정보 수정",
    description=(
        "전달한 필드만 부분 수정한다. 전부 선택 입력이며 회원가입 흐름과 무관하게 언제든 호출할 수 있다. "
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
) -> Response:
    updated_profile = await health_info_service.update_health_info(session, profile, update_data)
    return Response(_to_health_info_response(updated_profile).model_dump(), status_code=status.HTTP_200_OK)
