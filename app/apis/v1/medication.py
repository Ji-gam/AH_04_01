from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.medication_dto import (
    MedicationScheduleCreateRequest,
    MedicationScheduleResponse,
    MedicationScheduleUpdateRequest,
    QuickRegisterRequest,
    QuickRegisterResult,
    RecognitionConfirmRequest,
    RecognitionConfirmResult,
    RecognitionJobCreateResult,
    RecognitionResult,
)
from app.models.profiles import Profile
from app.services.medication_service import MedicationService

medication_router = APIRouter(tags=["Medications"])


@medication_router.post(
    "/recognition/jobs",
    response_model=RecognitionJobCreateResult,
    status_code=202,
    summary="알약/처방전/진료기록 인식 요청",
    description=(
        "비동기로 처방전/알약 이미지를 업로드하고 분석 작업을 시작합니다. "
        "`dummy_mode=true`로 요청하면 실제 OCR 호출 없이 결정적인 더미 인식 결과를 즉시 받을 수 있어, "
        "OCR 연동 상태와 무관하게 이후 확정/스케줄 등록 플로우를 테스트할 수 있습니다(T-MED-3)."
    ),
)
async def create_recognition_job(
    background_tasks: BackgroundTasks,
    source_type: Annotated[str, Form(...)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
    dummy_mode: Annotated[
        bool,
        Form(
            description=(
                "true로 요청하면 실제 OCR을 호출하지 않고 결정적인 더미 인식 결과(타이레놀정/아스피린정 후보)를 "
                "즉시 반환한다. QA가 OCR 연동 상태와 무관하게 이후 확정/스케줄 등록 플로우를 테스트할 때 사용."
            )
        ),
    ] = False,
) -> RecognitionJobCreateResult:
    service = MedicationService()
    file_bytes = await file.read()
    return await service.create_recognition_job(
        session=session,
        profile_id=profile.id,
        source_type=source_type,
        file_bytes=file_bytes,
        file_name=file.filename or "image.jpg",
        background_tasks=background_tasks,
        dummy_mode=dummy_mode,
    )


@medication_router.get(
    "/recognition/jobs/{job_id}",
    response_model=RecognitionResult,
    summary="인식 결과 조회",
    description="비동기 OCR 및 분석 작업 결과를 확인합니다.",
)
async def get_recognition_job(
    job_id: str,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecognitionResult:
    service = MedicationService()
    return await service.get_recognition_job(session, job_id, profile.id)


@medication_router.post(
    "/recognition/jobs/{job_id}/confirm",
    response_model=RecognitionConfirmResult,
    summary="사용자 최종 확인 → 복약 스케줄 자동 반영",
    description="사용자가 인식을 완료하고 최종 선택한 의약품 코드를 복약 스케줄에 반영합니다.",
)
async def confirm_recognition_job(
    job_id: str,
    body: RecognitionConfirmRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecognitionConfirmResult:
    service = MedicationService()
    return await service.confirm_recognition_job(
        session=session,
        job_id=job_id,
        profile_id=profile.id,
        selected_candidate_drug_code=body.selected_candidate_drug_code,
        confirmed_fields=body.confirmed_fields,
    )


@medication_router.get(
    "/medications",
    response_model=list[MedicationScheduleResponse],
    summary="등록된 복약 스케줄 목록",
    description="현재 프로필에 등록되어 활성화된 복약 스케줄 목록을 가져옵니다.",
)
async def list_medication_schedules(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MedicationScheduleResponse]:
    service = MedicationService()
    return await service.list_schedules(session, profile.id)


@medication_router.get(
    "/medications/search-dur",
    summary="의약품 DUR 및 효능 검색 API (SQLite Light)",
    description="Light SQLite 데이터베이스를 사용하여 제품명으로 검색하고 효능 및 금기사항과 쿼리 지연시간을 반환합니다.",
)
async def search_medications_dur(
    profile: Annotated[Profile, Depends(get_current_profile)],
    query: str = Query(..., min_length=1),
):
    import os
    import sqlite3
    import time

    start_time = time.perf_counter()

    # Resolve path dynamically using the location of this file
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "database",
        "dur_drug_light.db",
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    sql = """
    SELECT
        p.item_name,
        p.entp_name,
        e.efcy_qesitm,
        GROUP_CONCAT(DISTINCT r.rule_type || ': ' || r.prohbt_content) AS precautions
    FROM products p
    LEFT JOIN drugs_einfo e ON p.item_seq = e.item_seq
    LEFT JOIN dur_product_rules r ON p.item_seq = r.item_seq
    WHERE p.item_name LIKE ?
    GROUP BY p.item_seq
    LIMIT 15;
    """

    cursor.execute(sql, (f"%{query}%",))
    rows = cursor.fetchall()
    conn.close()

    end_time = time.perf_counter()
    elapsed_ms = (end_time - start_time) * 1000

    results = []
    for row in rows:
        results.append({
            "item_name": row[0],
            "entp_name": row[1],
            "efficacy": row[2] or "정보 없음",
            "precautions": row[3] or "특이사항 없음"
        })

    return {
        "elapsed_ms": round(elapsed_ms, 4),
        "results": results
    }


@medication_router.post(
    "/medications",
    response_model=MedicationScheduleResponse,
    status_code=201,
    summary="복약 스케줄 수동 등록",
    description="의약품 코드를 직접 선택하여 시간을 지정하고 복약 스케줄을 직접 등록합니다.",
)
async def create_manual_schedule(
    body: MedicationScheduleCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationScheduleResponse:
    service = MedicationService()
    return await service.create_manual_schedule(session, profile.id, body)


@medication_router.post(
    "/medications/quick-register",
    response_model=QuickRegisterResult,
    summary="약품명으로 바로 등록 (검색 단계 생략)",
    description=(
        "약품명을 입력해 검색→선택 2단계 없이 한 번에 복약 스케줄을 등록합니다. "
        "이름이 정확히 하나만 일치하면 즉시 등록되고, 전혀 일치하지 않으면 새 약품을 즉석 생성해서라도 "
        "등록을 막지 않습니다(T-MED-3). 여러 개가 부분일치하면 자동 등록하지 않고 후보 목록만 반환하며, "
        "이 경우 응답의 `candidates`를 `POST /medications`(drug_code 지정)로 다시 요청해 최종 등록해야 합니다."
    ),
)
async def quick_register_medication(
    body: QuickRegisterRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> QuickRegisterResult:
    service = MedicationService()
    return await service.quick_register_medication(session, profile.id, body.drug_name, body.times, body.hospital_name)


@medication_router.patch(
    "/medications/{schedule_id}",
    response_model=MedicationScheduleResponse,
    summary="복약 스케줄 부분 수정",
    description="전달한 필드(복용 시간 목록, 병원명)만 부분 수정합니다.",
)
async def update_medication_schedule(
    schedule_id: int,
    body: MedicationScheduleUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationScheduleResponse:
    service = MedicationService()
    return await service.update_schedule(session, profile.id, schedule_id, body)


@medication_router.delete(
    "/medications/{schedule_id}",
    status_code=204,
    summary="복약 스케줄 삭제",
    description="잘못 등록되었거나 더 이상 필요 없는 복약 스케줄을 삭제합니다.",
)
async def delete_medication_schedule(
    schedule_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = MedicationService()
    await service.delete_schedule(session, profile.id, schedule_id)


@medication_router.get(
    "/medications/search",
    summary="의약품 마스터 수동 검색",
    description="약품명 또는 외형 검색 fallback을 위한 검색창의 자동완성 API입니다.",
)
async def search_medications(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(..., min_length=1),
):
    service = MedicationService()
    return await service.search_medications(session, query)


@medication_router.get(
    "/medications/search-dur",
    summary="의약품 DUR 및 효능 검색 API (SQLite Light)",
    description="Light SQLite 데이터베이스를 사용하여 제품명으로 검색하고 효능 및 금기사항과 쿼리 지연시간을 반환합니다.",
)
async def search_medications_dur(
    profile: Annotated[Profile, Depends(get_current_profile)],
    query: str = Query(..., min_length=1),
):
    import os
    import sqlite3
    import time

    start_time = time.perf_counter()

    # Resolve path dynamically using the location of this file
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "database",
        "dur_drug_light.db",
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    sql = """
    SELECT
        p.item_name,
        p.entp_name,
        e.efcy_qesitm,
        GROUP_CONCAT(DISTINCT r.rule_type || ': ' || r.prohbt_content) AS precautions
    FROM products p
    LEFT JOIN drugs_einfo e ON p.item_seq = e.item_seq
    LEFT JOIN dur_product_rules r ON p.item_seq = r.item_seq
    WHERE p.item_name LIKE ?
    GROUP BY p.item_seq
    LIMIT 15;
    """

    cursor.execute(sql, (f"%{query}%",))
    rows = cursor.fetchall()
    conn.close()

    end_time = time.perf_counter()
    elapsed_ms = (end_time - start_time) * 1000

    results = []
    for row in rows:
        results.append({
            "item_name": row[0],
            "entp_name": row[1],
            "efficacy": row[2] or "정보 없음",
            "precautions": row[3] or "특이사항 없음"
        })

    return {
        "elapsed_ms": round(elapsed_ms, 4),
        "results": results
    }

