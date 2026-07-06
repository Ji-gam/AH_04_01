# backend/domains/auth/router.py
# API_Specification_v3.pdf [M1] 회원가입/로그인/로그아웃/토큰재발급
# 실제 JWT Access/Refresh 토큰 발급 로직이 들어있습니다 (더 이상 placeholder가 아닙니다!)
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from backend.domains.user.schema import SignupRequest, SignupResponse, TokenResponse
from backend.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/users/refresh"


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED, summary="회원가입")
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일 주소입니다.")

    new_user = User(
        email=data.email,
        password_hash=get_password_hash(data.password) if data.password else None,
        name=data.name,
        role_type=data.role_type,
        gender=data.gender,
        birth_date=data.birth_date,
        sns_provider=data.sns_provider,
        sns_id=data.sns_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "name": new_user.name,
        "role_type": new_user.role_type,
        "gender": new_user.gender,
        "birth_date": new_user.birth_date,
        "sns_provider": new_user.sns_provider,
        "created_at": new_user.created_at,
    }


@router.post("/login", response_model=TokenResponse, summary="로그인")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm은 username/password 필드를 씁니다.
    # v3 명세도 Body(Form Data)로 username=이메일 을 받는 구조라 그대로 맞습니다.
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.password_hash or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="이메일 또는 비밀번호가 일치하지 않습니다.")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    user.refresh_token = refresh_token
    db.commit()

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", summary="로그아웃")
def logout(response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.refresh_token = None
    db.commit()
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    return {"message": "성공적으로 로그아웃되었습니다."}


@router.post("/refresh", response_model=TokenResponse, summary="토큰 재발급")
def refresh(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 리프레시 토큰입니다.")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 리프레시 토큰입니다.")

    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    # DB에 저장된 refresh_token과 쿠키값이 일치하는지도 검증 (로그아웃된 토큰 재사용 방지)
    if not user or user.refresh_token != token:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 리프레시 토큰입니다.")

    new_access_token = create_access_token(user.id)
    return {"access_token": new_access_token, "token_type": "bearer"}
