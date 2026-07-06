from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse as Response
from fastapi.responses import RedirectResponse
from starlette.responses import Response as BaseResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import config
from app.core.config import Env
from app.dependencies.security import get_request_user
from app.dtos.auth import LoginRequest, LoginResponse, SignUpRequest, TokenRefreshResponse
from app.models.users import User
from app.services.auth import AuthService
from app.services.oauth import OAuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# [핀포인트 추가] 무차별 대입 공격(brute force) 방지용 속도 제한. IP 기준으로 셉니다.
limiter = Limiter(key_func=get_remote_address)


def _set_refresh_cookie(resp: BaseResponse, refresh_token) -> None:
    """로그인/재발급 양쪽에서 똑같이 쓰는 쿠키 세팅 로직을 함수로 뺐습니다.
    [핀포인트 버그 수정] 기존 코드는 expires에 access_token의 exp(짧음)를 넣고 있어서,
    refresh_token 쿠키가 refresh 토큰 자체보다 훨씬 일찍 브라우저에서 삭제되는 문제가 있었습니다.
    반드시 refresh_token 자신의 만료시각을 넣어야 합니다."""
    resp.set_cookie(
        key="refresh_token",
        value=str(refresh_token),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=refresh_token.payload["exp"],
    )


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")  # [핀포인트 추가] 가입 어뷰징 방지
async def signup(
    request: Request,
    body: SignUpRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    await auth_service.signup(body)
    return Response(content={"detail": "회원가입이 성공적으로 완료되었습니다."}, status_code=status.HTTP_201_CREATED)


@auth_router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")  # [핀포인트 추가] 무차별 대입 공격 방지
async def login(
    request: Request,
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.authenticate(body)
    tokens = await auth_service.login(
        user
    )  # [핀포인트 변경] 내부에서 refresh_token을 DB에도 저장하도록 auth_service.login이 수정됨
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
    )
    _set_refresh_cookie(resp, tokens["refresh_token"])
    return resp


@auth_router.get("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    auth_service: Annotated[AuthService, Depends(AuthService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")

    # [핀포인트 변경] 기존엔 서명만 검증하고 새 access_token만 내려줬는데,
    # 이제는 DB의 refresh_token과 실제로 일치하는지까지 확인하고, refresh_token 자체도 새로 발급(회전)합니다.
    tokens = await auth_service.rotate_refresh_token(refresh_token)
    resp = Response(
        content=TokenRefreshResponse(access_token=str(tokens["access_token"])).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    _set_refresh_cookie(resp, tokens["refresh_token"])
    return resp


@auth_router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    user: Annotated[User, Depends(get_request_user)],
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    """[핀포인트 추가] DB의 refresh_token을 지워서, 브라우저에 남아있는 쿠키가 더 이상 안 먹히게 만듭니다."""
    await auth_service.logout(user)
    resp = Response(content={"detail": "성공적으로 로그아웃되었습니다."}, status_code=status.HTTP_200_OK)
    resp.delete_cookie(key="refresh_token", domain=config.COOKIE_DOMAIN or None)
    return resp


# ------------------------------------------------------------------
# [핀포인트 추가] 소셜 로그인 (구글/네이버/카카오)
# 실제 Client ID/Secret이 .env에 채워지기 전까지는 ①단계(리다이렉트 주소 생성)까지만
# 정상 동작하고, ②단계(구글 등에 실제 토큰 요청)는 400으로 실패합니다 — 정상입니다.
# ------------------------------------------------------------------


@auth_router.get("/{provider}/login", summary="소셜 로그인 시작")
async def oauth_login(
    provider: str,
    oauth_service: Annotated[OAuthService, Depends(OAuthService)],
) -> RedirectResponse:
    authorize_url = oauth_service.build_authorize_url(provider)
    return RedirectResponse(url=authorize_url)


@auth_router.get("/{provider}/callback", summary="소셜 로그인 콜백")
async def oauth_callback(
    provider: str,
    code: str,
    oauth_service: Annotated[OAuthService, Depends(OAuthService)],
) -> RedirectResponse:
    user = await oauth_service.handle_callback(provider, code)
    tokens = await oauth_service.issue_tokens_for_social_login(user)

    redirect = RedirectResponse(url=config.FRONTEND_URL)
    _set_refresh_cookie(redirect, tokens["refresh_token"])
    return redirect
