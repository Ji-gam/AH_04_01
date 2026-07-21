from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse as Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.config import Env
from app.core.db.databases import get_db
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.dependencies.security import get_request_user
from app.dtos.auth import LoginRequest, LoginResponse, SignUpRequest, TokenRefreshResponse, WithdrawRequest
from app.models.users import User
from app.services.auth import AuthService
from app.services.oauth_clients import get_oauth_client, supported_providers
from app.services.social_auth import SocialAuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _login_response(tokens: dict[str, AccessToken | RefreshToken], status_code: int = status.HTTP_200_OK) -> Response:
    """Access Token은 body, Refresh Token은 httpOnly 쿠키 - 이메일 로그인/소셜 로그인 공통으로 쓴다."""
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status_code
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp


@auth_router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="이메일 회원가입",
    description="User(계정)를 생성하고, 동시에 본인 Profile(relation=SELF)을 자동으로 생성한다.",
    responses={
        status.HTTP_409_CONFLICT: {"description": "이메일 또는 휴대폰 번호가 이미 사용 중"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "비밀번호/생년월일/휴대폰번호 형식이 유효하지 않음"},
    },
)
async def signup(
    request: SignUpRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    await auth_service.signup(session, request)
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
    },
)
async def login(
    request: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.authenticate(session, request)
    tokens = await auth_service.login(session, user)
    return _login_response(tokens)


@auth_router.get(
    "/token/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="액세스 토큰 재발급",
    description=(
        "쿠키의 refresh_token으로 새 Access Token을 발급한다. 요청 본문은 없고, 쿠키만 있으면 된다. "
        "[로테이션] 이때 refresh_token 자체도 새 값으로 교체되고 쿠키가 갱신된다 - 예전 refresh_token은 "
        "즉시 무효화되어 다시 쓸 수 없다. 이미 무효화된 토큰으로 재시도하면(탈취 의심) 그 계정의 "
        "모든 세션이 강제 로그아웃된다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "refresh_token 쿠키가 없거나 만료/무효화됨"},
        status.HTTP_400_BAD_REQUEST: {"description": "refresh_token이 유효하지 않음(위조/형식 오류)"},
    },
)
async def token_refresh(
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    tokens = await auth_service.rotate_refresh_token(session, refresh_token)
    resp = Response(
        content=TokenRefreshResponse(access_token=str(tokens["access_token"])).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    description="refresh_token 쿠키를 무효화(revoke)하고 쿠키를 삭제한다. 쿠키가 없거나 이미 만료됐어도 항상 성공한다.",
)
async def logout(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    refresh_token_str = request.cookies.get("refresh_token")
    if refresh_token_str:
        await auth_service.logout(session, refresh_token_str)
    resp = Response(content=None, status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="refresh_token", domain=config.COOKIE_DOMAIN or None)
    return resp


@auth_router.delete(
    "/withdraw",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회원탈퇴",
    description=(
        "본인 확인용 현재 비밀번호를 재확인한 뒤, User(계정)와 본인 Profile(개인정보)을 즉시 완전 삭제한다. "
        "개인정보보호법상 탈퇴 시 지체없이 파기해야 하므로 소프트삭제가 아니라 하드삭제이며, 되돌릴 수 없다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "비밀번호가 올바르지 않음"},
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
    },
)
async def withdraw(
    request: WithdrawRequest,
    user: Annotated[User, Depends(get_request_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> None:
    await auth_service.withdraw(session, user, request.password)


@auth_router.get(
    "/{provider}/login",
    summary="소셜 로그인 시작",
    description="해당 provider의 동의 화면으로 리다이렉트한다. 지원 provider: "
    + ", ".join(supported_providers())
    + ".",
    responses={status.HTTP_404_NOT_FOUND: {"description": "지원하지 않는 provider"}},
)
async def social_login(provider: str) -> RedirectResponse:
    if provider not in supported_providers():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 provider입니다: {provider}")
    client = get_oauth_client(provider)
    return RedirectResponse(client.get_authorize_url())


@auth_router.get(
    "/{provider}/callback",
    summary="소셜 로그인 콜백",
    description=(
        "provider가 이 주소로 code를 담아 리다이렉트해온다. 기존 계정이면 로그인, 신규면 이 시점에 "
        "곧바로 계정을 생성한다(닉네임+이메일은 provider가 이미 주므로 별도 입력 화면 없음). "
        "처리 후 refresh_token 쿠키를 심고 FRONTEND_URL(홈)로 리다이렉트한다. "
        "브라우저 리다이렉트로만 동작해서 Swagger에서는 직접 테스트할 수 없다."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "지원하지 않는 provider"},
        status.HTTP_409_CONFLICT: {"description": "이미 다른 방식(이메일 등)으로 가입된 이메일"},
    },
)
async def social_callback(
    provider: str,
    code: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    social_auth_service: Annotated[SocialAuthService, Depends(SocialAuthService)],
) -> RedirectResponse:
    if provider not in supported_providers():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"지원하지 않는 provider입니다: {provider}")

    client = get_oauth_client(provider)
    userinfo = await client.fetch_userinfo(code)
    tokens = await social_auth_service.handle_callback(session, provider, userinfo)

    # Access Token은 body로 못 내려준다(브라우저 리다이렉트라 body를 못 읽음) - refresh_token 쿠키만
    # 심어두면, 프론트가 홈 로딩 시 useAuth 초기화 과정에서 자동으로 /auth/token/refresh를 호출해서
    # access_token을 받아간다(기존 새로고침 로그인유지 로직 재사용).
    redirect = RedirectResponse(config.FRONTEND_URL + "/")
    redirect.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return redirect
