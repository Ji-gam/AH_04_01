# backend/utils/security.py
#보안식별 초안!
import datetime
from jose import jwt, JWTError
from argon2 import PasswordHasher
from backend.core.config import settings

# 1. PasswordHasher 인스턴스 (보안 해싱용)
ph = PasswordHasher()

# --- [기존 서비스 보안 로직] ---
def get_password_hash(password: str) -> str:
    """평문 비밀번호를 Argon2 해시로 변환"""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력받은 비밀번호와 저장된 해시 비밀번호가 일치하는지 확인"""
    try:
        return ph.verify(hashed_password, plain_password)
    except:
        return False

# --- [기존 유틸 보안/보조 로직] ---
def anonymize_pii(text: str) -> str:
    """LLM API 전송 전 개인 식별 정보를 마스킹 처리합니다."""
    # 실제 구현 시에는 정규식 등을 사용하여 고도화 가능
    sensitive_keywords = ["홍길동", "김철수"] 
    masked_text = text
    for keyword in sensitive_keywords:
        masked_text = masked_text.replace(keyword, "***")
    return masked_text

# --- [JWT 인증] ---
# API_Specification_v3.pdf M1 기준: Access Token 30분, Refresh Token 14일
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 14


def create_access_token(user_id: int) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    """JWT 토큰을 디코드합니다. 만료/위조 시 None을 반환합니다."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def verify_token(token: str) -> bool:
    """토큰이 유효한지(서명/만료) 여부만 확인합니다."""
    return decode_token(token) is not None