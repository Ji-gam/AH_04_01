# backend/domains/user/router.py
# API_Specification_v3.pdf [M1] 회원 정보 조회/수정/탈퇴, 이메일 중복확인
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from .model import User
from .schema import UserMeResponse, UserMeUpdate

router = APIRouter()


def _time_to_str(t):
    return t.strftime("%H:%M:%S") if t else None


def _user_to_me_response(user: User) -> dict:
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "role_type": user.role_type,
        "gender": user.gender,
        "birth_date": user.birth_date,
        "use_voice_mode": user.use_voice_mode,
        "use_large_font": user.use_large_font,
        "wake_time": _time_to_str(user.wake_time),
        "breakfast_time": _time_to_str(user.breakfast_time),
        "lunch_time": _time_to_str(user.lunch_time),
        "dinner_time": _time_to_str(user.dinner_time),
        "bed_time": _time_to_str(user.bed_time),
    }


@router.get("/check-email", summary="이메일 중복 확인")
def check_email(email: str, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일 주소입니다.")
    return {"message": "사용 가능한 이메일입니다."}


@router.get("/me", response_model=UserMeResponse, summary="내 정보 및 개인화 설정 조회")
def get_me(current_user: User = Depends(get_current_user)):
    return _user_to_me_response(current_user)


@router.patch("/me", response_model=UserMeResponse, summary="내 정보 및 개인화 설정 수정")
def update_me(data: UserMeUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import datetime as dt
    TIME_FIELDS = {"wake_time", "breakfast_time", "lunch_time", "dinner_time", "bed_time"}
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in TIME_FIELDS and isinstance(value, str):
            value = dt.datetime.strptime(value, "%H:%M:%S").time() if value.count(":") == 2 else dt.datetime.strptime(value, "%H:%M").time()
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return _user_to_me_response(current_user)


@router.delete("/me", summary="회원 탈퇴")
def delete_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 연관 테이블은 model.py의 relationship에 cascade="all, delete-orphan"이 걸려있어 함께 삭제됩니다.
    db.delete(current_user)
    db.commit()
    return {"message": "회원 탈퇴 처리가 정상적으로 완료되었습니다."}
