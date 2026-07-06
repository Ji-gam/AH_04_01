# backend/domains/pwa_subscription/router.py
# API_Specification_v3.pdf [M2] 웹 푸시 구독 등록(Upsert)/해지
# ⚠️ 참고: 이 라우터는 "구독 정보 저장"까지만 합니다. 실제로 푸시 메시지를 발송하는 워커/스케줄러는
# 이 API 스펙 범위 밖이라 별도 구현이 필요합니다 (v3 명세서에도 발송 로직은 명시되어 있지 않음).
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import PwaSubscription
from .schema import SubscriptionCreate, SubscriptionResponse, SubscriptionDelete

router = APIRouter()


@router.post("", response_model=SubscriptionResponse, status_code=201, summary="푸시 구독 등록 (Upsert)")
def register_subscription(data: SubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(PwaSubscription).filter(PwaSubscription.endpoint_url == data.endpoint_url).first()
    if existing:
        existing.p256dh_key = data.p256dh_key
        existing.auth_key = data.auth_key
        existing.user_id = current_user.id
        db.commit()
        db.refresh(existing)
        sub = existing
    else:
        sub = PwaSubscription(user_id=current_user.id, **data.model_dump())
        db.add(sub)
        db.commit()
        db.refresh(sub)

    return {
        "subscription_id": sub.id,
        "user_id": sub.user_id,
        "endpoint_url": sub.endpoint_url,
        "updated_at": sub.updated_at,
    }


@router.delete("", summary="푸시 구독 해지")
def delete_subscription(data: SubscriptionDelete, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = db.query(PwaSubscription).filter(
        PwaSubscription.endpoint_url == data.endpoint_url,
        PwaSubscription.user_id == current_user.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="구독 정보를 찾을 수 없습니다.")
    db.delete(sub)
    db.commit()
    return {"message": "푸시 구독이 해지되었습니다."}
