# backend/domains/generated_guide/router.py
# API_Specification_v3.pdf [M10] LLM 맞춤형 가이드 자동 생성(비동기), 상세조회
# TODO(조원 구현): 실제 LLM 호출 및 비동기 작업 큐는 아직 없습니다.
# 지금은 요청 즉시 고정 문구로 가이드를 만들어 저장합니다. 나중에 create_guide 내부를
# 실제 LLM 프롬프트 호출로 교체하고, 필요하면 task_id 기반 비동기 처리로 바꾸면 됩니다.
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import GeneratedGuide
from .schema import GuideCreate, GuideTaskAccepted, GuideResponse

router = APIRouter()


@router.post("", response_model=GuideTaskAccepted, status_code=202, summary="LLM 맞춤형 가이드 자동 생성")
def create_guide(data: GuideCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # TODO: 실제로는 여기서 task_id만 즉시 반환하고, 백그라운드 워커가 LLM 호출 후 DB에 결과를 채워야 합니다.
    placeholder_content = f"[플레이스홀더] {data.guide_type} 가이드 - 실제 LLM 연동 전까지 이 문구가 대신 저장됩니다."
    new_guide = GeneratedGuide(
        user_id=current_user.id,
        record_id=data.record_id,
        guide_type=data.guide_type,
        content=placeholder_content,
    )
    db.add(new_guide)
    db.commit()

    return {"task_id": f"guide_task_{uuid.uuid4().hex[:10]}", "status": "PROCESSING", "created_at": datetime.datetime.utcnow()}


@router.get("/{guide_id}", response_model=GuideResponse, summary="자동 생성 가이드 상세 조회")
def get_guide(guide_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    guide = db.query(GeneratedGuide).filter(
        GeneratedGuide.id == guide_id, GeneratedGuide.user_id == current_user.id
    ).first()
    if not guide:
        raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다.")
    return {
        "guide_id": guide.id,
        "user_id": guide.user_id,
        "record_id": guide.record_id,
        "guide_type": guide.guide_type,
        "content": guide.content,
        "created_at": guide.created_at,
    }
