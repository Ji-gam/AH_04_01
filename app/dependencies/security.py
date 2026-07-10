from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.models.profiles import Profile
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


async def get_request_user(
    credential: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credential.credentials
    verified = JwtService().verify_jwt(token=token, token_type="access")
    user_id = verified.payload["user_id"]
    user = await UserRepository().get_user(session, user_id)
    if not user:
        raise HTTPException(detail="Authenticate Failed.", status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def get_current_profile(
    credential: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Profile:
    """도메인 라우터(복약, 채팅 등)는 이 의존성으로 곧바로 profile_id 기준 스코핑을 한다."""
    token = credential.credentials
    verified = JwtService().verify_jwt(token=token, token_type="access")
    profile_id = verified.payload["profile_id"]
    profile = await ProfileRepository().get_profile(session, profile_id)
    if not profile:
        raise HTTPException(detail="Authenticate Failed.", status_code=status.HTTP_401_UNAUTHORIZED)
    return profile


async def get_current_profile_optional(
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(security_optional)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Profile | None:
    """비로그인 사용자도 접근 가능한 공개 엔드포인트용(T-LLM-3 "정보" 탭 등).
    토큰이 없거나 검증에 실패하면 예외를 던지지 않고 None(익명 처리)을 반환한다."""
    if credential is None:
        return None
    try:
        verified = JwtService().verify_jwt(token=credential.credentials, token_type="access")
        return await ProfileRepository().get_profile(session, verified.payload["profile_id"])
    except Exception:
        return None
