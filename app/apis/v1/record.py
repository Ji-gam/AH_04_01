from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.record import OcrTaskAccepted, OcrTaskStatus, RecordCreate, RecordCreateResponse, RecordDetailResponse
from app.models.users import User
from app.services.record_service import RecordService

record_router = APIRouter(prefix="/records", tags=["records"])


@record_router.post("/ocr", response_model=OcrTaskAccepted, status_code=status.HTTP_202_ACCEPTED)
async def handle_ocr(
    user: Annotated[User, Depends(get_request_user)],
    record_service: Annotated[RecordService, Depends(RecordService)],
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()],
) -> Response:
    task = await record_service.create_ocr_task(user, file.filename or "unknown_filename")
    response_data = {
        "success": True,
        "data": {
            "task_id": task.task_id,
            "status": "PROCESSING",
            "created_at": task.created_at.isoformat(),
        },
        "message": "OCR 분석 요청이 수락되었습니다.",
    }
    return Response(response_data, status_code=status.HTTP_202_ACCEPTED)


@record_router.get("/ocr/status/{task_id}", response_model=OcrTaskStatus, status_code=status.HTTP_200_OK)
async def get_ocr_status(
    task_id: str,
    user: Annotated[User, Depends(get_request_user)],
    record_service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    task = await record_service.get_ocr_task(task_id)
    response_data = {
        "success": True,
        "data": {
            "task_id": task.task_id,
            "status": task.status,
            "record_id": task.record_id,
            "image_s3_url": task.image_s3_url,
            "ocr_raw_json": task.ocr_raw_json,
        },
        "message": "OCR 상태 정보를 조회했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)


@record_router.post("", response_model=RecordCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    data: RecordCreate,
    user: Annotated[User, Depends(get_request_user)],
    record_service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    new_record = await record_service.create_medical_record(user, data)
    response_data = {
        "success": True,
        "data": {
            "record_id": new_record.id,
            "user_id": new_record.user_id,
            "document_type": new_record.document_type,
            "visit_date": new_record.visit_date.isoformat() if new_record.visit_date else None,
            "diagnosis_name": new_record.diagnosis_name,
            "uploaded_at": new_record.uploaded_at.isoformat(),
        },
        "message": "진료 기록을 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)


@record_router.get("/{record_id}", response_model=RecordDetailResponse, status_code=status.HTTP_200_OK)
async def get_record_detail(
    record_id: int,
    user: Annotated[User, Depends(get_request_user)],
    record_service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    record = await record_service.get_medical_record_detail(user, record_id)

    medications_out = []
    for m in record.medications:
        medications_out.append(
            {
                "id": m.id,
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
            }
        )

    response_data = {
        "success": True,
        "data": {
            "id": record.id,
            "document_type": record.document_type,
            "hospital_name": record.hospital_name,
            "pharmacy_name": record.pharmacy_name,
            "diagnosis_name": record.diagnosis_name,
            "diagnosis_code": record.diagnosis_code,
            "visit_date": record.visit_date.isoformat() if record.visit_date else None,
            "receipt_amount": record.receipt_amount,
            "medications": medications_out,
        },
        "message": "진료 기록 상세 정보를 조회했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)
