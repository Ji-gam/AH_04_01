# backend/core/dependencies.py
# 공통 의존성 정의 (인증, DB 세션 등)
# [v3 반영] 더 이상 고정 유저를 반환하지 않고, 실제로 Authorization: Bearer <token> 헤더의
# JWT Access Token을 검증해서 로그인한 유저를 찾아줍니다.
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.domains.user.model import User
from backend.utils.security import decode_token

# tokenUrl은 Swagger UI의 "Authorize" 버튼 안내용입니다 (실제 요청 경로와 무관하게 동작 가능)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증되지 않은 사용자입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user
