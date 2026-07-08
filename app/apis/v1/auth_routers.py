from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse as Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response as BaseResponse

from app.core import config
from app.core.config import Env
from app.core.db.databases import get_db
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.rate_limit import limiter
from app.dependencies.security import get_request_user
from app.dtos.auth import (
    LoginRequest,
    LoginResponse,
    SignUpRequest,
    SocialSignupCompleteRequest,
    TokenRefreshResponse,
    WithdrawRequest,
)
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService
from app.services.jwt import JwtService
from app.services.oauth import OAuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _exp_to_datetime(exp_epoch_seconds: int) -> datetime:
    """[T-AUTH-4 버그수정] JWT의 exp(절대 Unix epoch 초)를 진짜 datetime으로 바꾼다.
    Response.set_cookie(expires=...)에 정수를 그대로 넘기면 "지금부터 N초 후"로
    해석되어(절대시각이 아니라 상대시간!), exp 같은 큰 절대시각 값을 넣으면 수십~수백년
    뒤로 계산되는 버그가 생긴다. datetime으로 바꿔서 넘겨야 절대시각으로 정확히 반영된다.
    """
    return datetime.fromtimestamp(exp_epoch_seconds, tz=UTC)


def _set_refresh_cookie(response: BaseResponse, refresh_token: AccessToken | RefreshToken) -> None:
    """login/oauth_callback/token_refresh(회전)/complete-signup 네 곳에서 공통으로 쓰는 쿠키 설정.
    한 곳에서만 관리해야 예전처럼 "한 곳은 고치고 한 곳은 안 고치는" 버그가 안 생긴다."""
    response.set_cookie(
        key="refresh_token",
        value=str(refresh_token),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=_exp_to_datetime(refresh_token.payload["exp"]),
    )


@auth_router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="이메일 회원가입",
    description="User(계정)를 생성하고, 동시에 본인 Profile(relation=SELF)을 자동으로 생성한다.",
    responses={
        status.HTTP_409_CONFLICT: {"description": "이메일 또는 휴대폰 번호가 이미 사용 중"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "비밀번호/생년월일/휴대폰번호/동의 항목이 유효하지 않음"
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "[T-AUTH-6] 같은 IP에서 1분에 5회 초과 요청"},
    },
)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    request_body: SignUpRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    await auth_service.signup(session, request_body)
    return Response(content={"detail": "회원가입이 성공적으로 완료되었습니다."}, status_code=status.HTTP_201_CREATED)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="로그인",
    description=(
        "이메일/비밀번호를 검증하고 JWT를 발급한다. Access Token은 응답 body로 오고, "
        "Refresh Token은 httpOnly 쿠키(Set-Cookie: refresh_token)로 내려간다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "이메일 또는 비밀번호가 올바르지 않음"},
        status.HTTP_423_LOCKED: {"description": "비활성화된 계정"},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "[T-AUTH-6] 같은 IP에서 1분에 5회 초과 요청"},
    },
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    request_body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.authenticate(session, request_body)
    tokens = await auth_service.login(session, user)
    resp = Response(
        content=LoginResponse(
            access_token=str(tokens["access_token"]),
            profile_id=tokens["access_token"].payload["profile_id"],
        ).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    _set_refresh_cookie(resp, tokens["refresh_token"])
    return resp


@auth_router.get(
    "/token/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="액세스 토큰 재발급",
    description=(
        "쿠키의 refresh_token으로 새 Access Token을 발급한다. 요청 본문은 없고, 쿠키만 있으면 된다. "
        "[T-AUTH-3] JWT 서명이 유효해도 DB에 저장된 최신 refresh_token과 다르면(로그아웃했거나 이미 "
        "교체된 옛 토큰이면) 401로 거부한다. "
        "[T-AUTH-5 회전] 호출할 때마다 refresh_token 자체도 새로 발급하고 DB의 이전 값을 즉시 "
        "교체한다 — 탈취된 refresh_token이 있어도 정상 사용자가 먼저 한 번 갱신하면 그 훔친 토큰은 "
        "곧바로 못 쓰게 된다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "refresh_token 쿠키가 없거나 만료됨, 또는 이미 로그아웃/회전되어 무효화됨"
        },
        status.HTTP_400_BAD_REQUEST: {"description": "refresh_token이 유효하지 않음(위조/형식 오류)"},
    },
)
async def token_refresh(
    session: Annotated[AsyncSession, Depends(get_db)],
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    user_repo: Annotated[UserRepository, Depends(UserRepository)],
    profile_repo: Annotated[ProfileRepository, Depends(ProfileRepository)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")

    verified_rt = jwt_service.verify_jwt(token=refresh_token, token_type="refresh")
    user = await user_repo.get_by_valid_refresh_token(session, verified_rt.payload["user_id"], refresh_token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이미 로그아웃되었거나 만료된 토큰입니다.")

    profile = await profile_repo.get_profile(session, verified_rt.payload["profile_id"])
    if profile is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다.")

    new_tokens = jwt_service.issue_jwt_pair(user, profile)
    await user_repo.update_refresh_token(session, user.id, str(new_tokens["refresh_token"]))
    await session.commit()

    access_token = new_tokens["access_token"]
    resp = Response(
        content=TokenRefreshResponse(
            access_token=str(access_token),
            profile_id=access_token.payload["profile_id"],
        ).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    _set_refresh_cookie(resp, new_tokens["refresh_token"])
    return resp


@auth_router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="로그아웃",
    description=(
        "[T-AUTH-3] DB에 저장된 refresh_token을 실제로 무효화한다. Authorization: Bearer 헤더 필요. "
        "이후 브라우저에 refresh_token 쿠키가 남아있어도 /auth/token/refresh가 401로 거부한다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Access Token이 없거나 유효하지 않음"}},
)
async def logout(
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
    current_user: Annotated[User, Depends(get_request_user)],
) -> Response:
    await auth_service.logout(session, current_user.id)
    resp = Response(content={"detail": "성공적으로 로그아웃되었습니다."}, status_code=status.HTTP_200_OK)
    resp.delete_cookie(key="refresh_token", domain=config.COOKIE_DOMAIN or None)
    return resp


@auth_router.delete(
    "/withdraw",
    status_code=status.HTTP_200_OK,
    summary="회원탈퇴",
    description=(
        "[T-AUTH-8] User(+cascade로 Profile)를 즉시 삭제한다(소프트삭제 아님 - 개인정보보호법상 "
        "탈퇴 시 지체없이 파기 의무). LOCAL 계정은 비밀번호 재확인이 필수이고, 소셜 계정은 "
        "비밀번호가 없으므로 생략 가능하다(Authorization: Bearer만으로 진행)."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "LOCAL 계정인데 비밀번호가 없거나 일치하지 않음"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Access Token이 없거나 유효하지 않음"},
    },
)
async def withdraw(
    request_body: WithdrawRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
    current_user: Annotated[User, Depends(get_request_user)],
) -> Response:
    await auth_service.withdraw(session, current_user, request_body.password)
    resp = Response(content={"detail": "회원 탈퇴가 완료되었습니다."}, status_code=status.HTTP_200_OK)
    resp.delete_cookie(key="refresh_token", domain=config.COOKIE_DOMAIN or None)
    return resp


# ------------------------------------------------------------------
# 소셜 로그인 (구글/네이버/카카오)
# [T-AUTH-7] 신규 가입자는 콜백에서 바로 계정을 만들지 않는다 - 우리 서비스 약관에 동의하고
# 나머지 정보(성별/생일/휴대폰번호)를 입력해야(POST .../complete-signup) 비로소 계정이 생긴다.
# 이미 가입되어 있던 사용자(재로그인)는 예전에 이미 동의했으므로 곧바로 로그인 처리된다.
# ------------------------------------------------------------------


@auth_router.get(
    "/{provider}/login",
    summary="소셜 로그인 시작",
    description="provider는 google/naver/kakao 중 하나. 해당 로그인 화면으로 리다이렉트한다.",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "지원하지 않는 provider (google/naver/kakao 외)"},
    },
)
async def oauth_login(
    provider: str,
    oauth_service: Annotated[OAuthService, Depends(OAuthService)],
) -> RedirectResponse:
    authorize_url = oauth_service.build_authorize_url(provider)
    return RedirectResponse(url=authorize_url)


@auth_router.get(
    "/{provider}/callback",
    summary="소셜 로그인 콜백",
    description=(
        "구글/네이버/카카오가 인가 코드(code)와 함께 호출하는 콜백. "
        "기존 사용자(이미 이 소셜계정으로 가입했거나, 이메일이 같은 로컬 계정이 있음)면 곧바로 "
        "로그인 처리하고 FRONTEND_URL로 리다이렉트한다(refresh_token 쿠키 포함). "
        "완전 신규 사용자면 계정을 만들지 않고, `{FRONTEND_URL}/social-signup?pending_token=...` "
        "로 리다이렉트한다 - 프론트는 이 파라미터가 있으면 약관동의+정보입력 화면을 띄워야 한다."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "지원하지 않는 provider (google/naver/kakao 외)"},
        status.HTTP_400_BAD_REQUEST: {
            "description": "제공자 토큰 발급 실패(코드 만료/재사용 등) 또는 사용자 식별값을 받지 못함"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "기존 계정 연결 과정에서 Profile을 찾지 못함(데이터 정합성 오류)"
        },
    },
)
async def oauth_callback(
    provider: str,
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    oauth_service: Annotated[OAuthService, Depends(OAuthService)],
) -> RedirectResponse:
    result = await oauth_service.handle_callback(session, provider, code)

    if not result.is_new_signup:
        assert result.tokens is not None
        redirect = RedirectResponse(url=config.FRONTEND_URL)
        _set_refresh_cookie(redirect, result.tokens["refresh_token"])
        return redirect

    # 신규 가입자: 계정 미생성 상태. 프론트의 약관동의+정보입력 화면으로 보낸다.
    assert result.pending_token is not None
    query = urlencode(
        {
            "pending_token": str(result.pending_token),
            "provider": result.provider or "",
            "email": result.email or "",
            "name": result.name or "",
        }
    )
    return RedirectResponse(url=f"{config.FRONTEND_URL}/social-signup?{query}")


@auth_router.post(
    "/{provider}/complete-signup",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="소셜 가입 완료 (약관동의+정보입력 이후)",
    description=(
        "[T-AUTH-7] /callback에서 받은 pending_token과 함께, 약관동의+성별/생년월일/휴대폰번호를 "
        "실어서 호출한다. 이 시점에 비로소 User+Profile이 실제로 생성되고, 로그인과 동일하게 "
        "JWT가 발급된다(Access Token은 body, Refresh Token은 쿠키)."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "pending_token이 유효하지 않음(위조/형식 오류)"},
        status.HTTP_401_UNAUTHORIZED: {"description": "pending_token 유효시간(10분) 만료"},
        status.HTTP_409_CONFLICT: {"description": "이미 가입 완료된 계정이거나, 이메일/휴대폰번호가 이미 사용 중"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "생년월일/휴대폰번호/동의 항목이 유효하지 않음"},
    },
)
async def complete_social_signup(
    request_body: SocialSignupCompleteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    oauth_service: Annotated[OAuthService, Depends(OAuthService)],
) -> Response:
    tokens = await oauth_service.complete_social_signup(
        session,
        pending_token=request_body.pending_token,
        name=request_body.name,
        gender=request_body.gender,
        birth_date=request_body.birth_date,
        phone_number=request_body.phone_number,
        agreements=request_body.agreements,
    )
    resp = Response(
        content=LoginResponse(
            access_token=str(tokens["access_token"]),
            profile_id=tokens["access_token"].payload["profile_id"],
        ).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )
    _set_refresh_cookie(resp, tokens["refresh_token"])
    return resp
