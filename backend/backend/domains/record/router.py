# backend/domains/record/router.py
# API_Specification_v3.pdf [M5] OCR 처리, 진료기록 등록/조회
# ⚠️ [단순화 안내] 실제 CLOVA OCR 호출, S3 업로드, 비동기 작업 큐(Celery 등)는 아직 없습니다.
# 여기서는 API 계약(요청/응답 형태, task_id 패턴)만 명세와 동일하게 맞춰두고,
# 내부적으로는 즉시(동기) 처리한 뒤 상태를 SUCCESS로 저장합니다.
# 나중에 실제 OCR/S3/큐를 붙일 때 이 파일의 handle_ocr 내부 로직만 교체하면 됩니다.
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from backend.domains.medication.model import Medication
from .model import MedicalRecord, RecordMedicationMapping, OcrTask
from .schema import RecordCreate, RecordCreateResponse, RecordDetailResponse, OcrTaskAccepted, OcrTaskStatus

router = APIRouter()


@router.post("/ocr", response_model=OcrTaskAccepted, status_code=202, summary="처방전/약봉투 이미지 OCR 분석")
async def handle_ocr(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task_id = f"ocr_task_{uuid.uuid4().hex[:12]}"

    # TODO(실제 연동 시 교체): S3 업로드 + CLOVA OCR 호출
    fake_image_url = f"https://healthai-storage.example.com/records/{current_user.id}/{file.filename}"
    fake_ocr_result = {
        "hospital_name": "미인식(수동 확인 필요)",
        "pharmacy_name": None,
        "diagnosis_name": None,
        "medications_detected": [],
    }

    task = OcrTask(
        task_id=task_id,
        status="SUCCESS",  # 실제 큐가 없어 즉시 완료 처리
        image_s3_url=fake_image_url,
        ocr_raw_json=fake_ocr_result,
    )
    db.add(task)
    db.commit()

    return {"task_id": task_id, "status": "PROCESSING", "created_at": datetime.datetime.utcnow()}


@router.get("/ocr/status/{task_id}", response_model=OcrTaskStatus, summary="OCR 처리 상태 조회")
def get_ocr_status(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(OcrTask).filter(OcrTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="해당 task_id를 찾을 수 없습니다.")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "record_id": task.record_id,
        "image_s3_url": task.image_s3_url,
        "ocr_raw_json": task.ocr_raw_json,
    }


def _calc_initial_remaining(med: dict) -> int:
    device_type = med.get("device_type")
    if device_type == "MULTI_DOSE_PEN":
        return med.get("total_clicks_or_doses") or 0
    return med.get("total_prescribed_quantity") or 1


@router.post("", response_model=RecordCreateResponse, status_code=201, summary="진료 및 처방 기록 등록")
def create_record(data: RecordCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record_data = data.model_dump(exclude={"medications"})
    new_record = MedicalRecord(**record_data, user_id=current_user.id)
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    for med in data.medications:
        medication = db.query(Medication).filter(Medication.id == med.medication_id).first()
        if not medication:
            raise HTTPException(status_code=404, detail=f"medication_id={med.medication_id} 를 찾을 수 없습니다.")
        med_dict = med.model_dump()
        mapping = RecordMedicationMapping(
            record_id=new_record.id,
            **med_dict,
            remaining_quantity=_calc_initial_remaining(med_dict),
        )
        db.add(mapping)
    db.commit()

    return {
        "record_id": new_record.id,
        "user_id": new_record.user_id,
        "document_type": new_record.document_type,
        "visit_date": new_record.visit_date,
        "diagnosis_name": new_record.diagnosis_name,
        "uploaded_at": new_record.uploaded_at,
    }


@router.get("/{record_id}", response_model=RecordDetailResponse, summary="진료 및 처방 기록 상세 조회")
def get_record(record_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    record = db.query(MedicalRecord).filter(
        MedicalRecord.id == record_id, MedicalRecord.user_id == current_user.id
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="진료 기록을 찾을 수 없거나 접근 권한이 없습니다.")

    medications_out = []
    for m in record.medications:
        medications_out.append({
            "mapping_id": m.id,
            "medication_id": m.medication_id,
            "medication_name": m.medication.medication_name if m.medication else "알 수 없음",
            "dosage_per_take": m.dosage_per_take,
            "takes_per_day": m.takes_per_day,
            "duration_days": m.duration_days,
            "instruction": m.instruction,
            "device_type": m.device_type,
            "total_clicks_or_doses": m.total_clicks_or_doses,
            "total_prescribed_quantity": m.total_prescribed_quantity,
            "remaining_quantity": m.remaining_quantity,
        })

    return {
        "record_id": record.id,
        "document_type": record.document_type,
        "hospital_name": record.hospital_name,
        "pharmacy_name": record.pharmacy_name,
        "diagnosis_name": record.diagnosis_name,
        "diagnosis_code": record.diagnosis_code,
        "visit_date": record.visit_date,
        "receipt_amount": record.receipt_amount,
        "medications": medications_out,
    }
