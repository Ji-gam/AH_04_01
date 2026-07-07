from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.config import Env
from app.core.db.databases import get_db
from app.dtos.auth import LoginRequest, LoginResponse, SignUpRequest, TokenRefreshResponse
from app.services.auth import AuthService
from app.services.jwt import JwtService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


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
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
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


@auth_router.get(
    "/token/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="액세스 토큰 재발급",
    description="쿠키의 refresh_token으로 새 Access Token을 발급한다. 요청 본문은 없고, 쿠키만 있으면 된다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "refresh_token 쿠키가 없거나 만료됨"},
        status.HTTP_400_BAD_REQUEST: {"description": "refresh_token이 유효하지 않음(위조/형식 오류)"},
    },
)
async def token_refresh(
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    access_token = jwt_service.refresh_jwt(refresh_token)
    return Response(
        content=TokenRefreshResponse(access_token=str(access_token)).model_dump(), status_code=status.HTTP_200_OK
    )
