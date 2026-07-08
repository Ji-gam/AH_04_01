from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile, get_request_user
from app.dtos.users import BiometricInfoRequest, UserInfoResponse, UserUpdateRequest
from app.models.profiles import Disease, Profile
from app.models.users import User
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
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        diagnosis_history=[Disease(d) for d in (profile.diagnosis_history or [])],
        family_history=[Disease(d) for d in (profile.family_history or [])],
        created_at=user.created_at,
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
        "전달한 필드만 부분 수정한다. name/phone_number/birthday/gender는 Profile에, "
        "email은 User에 반영되고, 둘을 합친 최신 정보를 반환한다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_409_CONFLICT: {"description": "변경하려는 이메일/휴대폰 번호가 이미 사용 중"},
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


@user_router.patch(
    "/me/biometric-info",
    response_model=UserInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="내 생체정보 입력/수정",
    description=(
        "[T-PROFILE-1] 회원가입 직후 별도 화면(키/체중/진단병력/가족력)에서 호출한다. "
        "전달한 필드만 부분 수정하며, diagnosis_history/family_history에 빈 리스트([])를 명시적으로 "
        "보내면 '해당 없음'으로 저장된다(필드 자체를 안 보내면 기존 값 유지)."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "키/체중이 허용 범위를 벗어나거나 질환 값이 5대질환 목록에 없음"
        },
    },
)
async def update_user_biometric_info(
    update_data: BiometricInfoRequest,
    user: Annotated[User, Depends(get_request_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    user_manage_service: Annotated[UserManageService, Depends(UserManageService)],
) -> Response:
    updated_user, updated_profile = await user_manage_service.update_biometric_info(session, user, profile, update_data)
    return Response(_to_user_info_response(updated_user, updated_profile).model_dump(), status_code=status.HTTP_200_OK)
