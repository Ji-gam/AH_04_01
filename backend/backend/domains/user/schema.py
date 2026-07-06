# backend/domains/user/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None  # 소셜 로그인 시 없을 수 있음
    name: str
    role_type: str = "PATIENT"
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    sns_provider: str = "LOCAL"
    sns_id: Optional[str] = None


class SignupResponse(BaseModel):
    user_id: int
    email: str
    name: str
    role_type: str
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    sns_provider: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True
        # DB 컬럼명(id)과 응답 필드명(user_id)이 달라서 매핑이 필요합니다.
        # SQLAlchemy 객체를 그대로 넣지 말고, 라우터에서 dict로 변환해서 반환하세요.


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    user_id: int
    email: str
    name: str
    role_type: str
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    use_voice_mode: bool = False
    use_large_font: bool = False
    wake_time: Optional[str] = None
    breakfast_time: Optional[str] = None
    lunch_time: Optional[str] = None
    dinner_time: Optional[str] = None
    bed_time: Optional[str] = None


class UserMeUpdate(BaseModel):
    role_type: Optional[str] = None
    use_voice_mode: Optional[bool] = None
    use_large_font: Optional[bool] = None
    wake_time: Optional[str] = None
    breakfast_time: Optional[str] = None
    lunch_time: Optional[str] = None
    dinner_time: Optional[str] = None
    bed_time: Optional[str] = None
