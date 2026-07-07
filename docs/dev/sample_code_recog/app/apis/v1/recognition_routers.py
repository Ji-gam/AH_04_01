"""
Router 레이어 규칙 (auth_routers.py와 동일): HTTP 처리만, 판단 없음.
실제 위치: app/apis/v1/recognition_routers.py (레이어 우선 구조, CODING_RULES.md 2번)

실제 api_spec_core_v1.yaml의 /recognition/jobs/{job_id}/confirm을 단순화한 데모.
job_id로 실제 OCR 결과를 조회하는 부분은 생략하고, 확정된 drug_name을 바로 받는 형태로 축약했다.
"""

from fastapi import APIRouter

from app.dtos.recognition import RecognitionConfirmResult
from app.services.recognition_service import RecognitionService

router = APIRouter(prefix="/recognition", tags=["Recognition"])


@router.post("/confirm-demo", response_model=RecognitionConfirmResult)
def confirm_recognition(drug_name: str) -> RecognitionConfirmResult:
    service = RecognitionService()
    guide_cards = service.generate_guide_cards(drug_name)
    return RecognitionConfirmResult(status="confirmed", guide_cards=guide_cards)
