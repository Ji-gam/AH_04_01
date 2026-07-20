from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.medication_dto import (
    FoodInteractionCheckResult,
    InteractionCheckResult,
    MedicationScheduleCreateRequest,
    MedicationScheduleResponse,
    MedicationScheduleUpdateRequest,
    QuickRegisterRequest,
    QuickRegisterResult,
    RecognitionConfirmForFamilyRequest,
    RecognitionConfirmRequest,
    RecognitionConfirmResult,
    RecognitionJobCreateResult,
    RecognitionResult,
)
from app.models.profiles import Profile
from app.repositories.dur_drug_repository import DrugProfile, DurDrugRepository
from app.services import medication_open_api_client
from app.services.medication_service import MedicationService, _strip_trailing_dosage

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
    "/medications/interactions",
    response_model=InteractionCheckResult,
    summary="등록약 간 병용금기(약물 상호작용) 체크",
    description=(
        "현재 프로필에 등록된 약들을 서로 대조해 식약처 병용금기 DUR 데이터에서 페어로 확인되는 "
        "조합이 있으면 경고 목록으로 반환합니다. 지병(질병-성분) 기준 금기는 다루지 않으며, "
        "등록약이 2개 미만이거나 품목기준코드(item_seq)가 없는 약뿐이면 빈 결과를 반환합니다(T-MED-2-2)."
    ),
)
async def check_medication_interactions(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InteractionCheckResult:
    service = MedicationService()
    return await service.check_interactions(session, profile.id)


@medication_router.get(
    "/medications/food-interactions",
    response_model=FoodInteractionCheckResult,
    summary="등록약 기준 음식/음주 주의사항 체크",
    description=(
        "현재 프로필에 등록된 약 전체를 대상으로 식약처 e약은요 상호작용 문항(intrcQesitm)에서 "
        "음식/음주 관련 주의사항을 모아 반환합니다. OCR로 등록했든 수동으로 등록했든 상관없이 "
        "등록된 모든 약이 대상입니다(T-DOC-2)."
    ),
)
async def check_medication_food_interactions(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FoodInteractionCheckResult:
    service = MedicationService()
    return await service.check_food_interactions(session, profile.id)


async def _query_mysql_dur_profiles(
    session: AsyncSession, dur_repo: DurDrugRepository, query: str, stripped_query: str | None
) -> list[DrugProfile]:
    """MySQL 품목명은 'mg'가 아니라 '밀리그램' 등 한글 단위 표기라, OCR/사용자 입력이
    'NN mg' 접미사로 끝나면 그대로는 매칭이 안 될 수 있다 — 접미사를 뗀 이름으로 재시도한다."""
    profiles = await dur_repo.find_drug_info(session, query)
    if not profiles and stripped_query:
        profiles = await dur_repo.find_drug_info(session, stripped_query)
    return profiles[:15]


def _build_dur_result(profile: DrugProfile) -> dict:
    efficacy = (profile.efficacy or "").strip()
    precaution_parts = [profile.precautions] + [
        f"{rule['rule_type']}: {rule['prohbt_content']}" for rule in profile.dur_rules if rule.get("prohbt_content")
    ]
    precautions = " ".join(p.strip() for p in precaution_parts if p and p.strip())
    return {
        "item_name": profile.item_name,
        "entp_name": profile.entp_name,
        "efficacy": efficacy or "정보 없음",
        "precautions": precautions or "특이사항 없음",
    }


def _has_content(result: dict) -> bool:
    return result["efficacy"] != "정보 없음" or result["precautions"] != "특이사항 없음"


def _drop_empty_duplicates(results: list[dict]) -> list[dict]:
    """같은 이름으로 여러 품목이 매칭될 때(제형/제조사 차이 등) 그중 일부만 효능·주의사항이
    있으면, 내용이 하나도 없는 나머지는 노이즈이므로 뺀다. 반대로 매칭된 품목 전부에 내용이
    없으면(이 약 자체의 데이터가 아직 없는 경우) — 찾은 품목명만이라도 그대로 보여주는 게
    "못 찾았다"는 잘못된 인상을 주는 것보다 낫다."""
    if any(_has_content(r) for r in results):
        return [r for r in results if _has_content(r)]
    return results


@medication_router.get(
    "/medications/search-dur",
    summary="의약품 DUR 및 효능 검색 API (MySQL + 공공데이터 폴백)",
    description=(
        "MySQL 품목 마스터(`dur_prod_master_list`+`drugs_data`)에서 제품명으로 먼저 검색하고, 결과가 "
        "없으면 식약처 공공데이터포털(e약은요) API로 실시간 폴백한다. 결과가 끝까지 없으면 "
        "`not_found_reason`에 어디까지 찾아봤는지가 담긴다."
    ),
)
async def search_medications_dur(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(..., min_length=1),
):
    import time

    start_time = time.perf_counter()

    stripped_query = _strip_trailing_dosage(query)

    dur_repo = DurDrugRepository()
    profiles = await _query_mysql_dur_profiles(session, dur_repo, query, stripped_query)
    results = [_build_dur_result(p) for p in profiles]

    # MySQL 품목 마스터는 품목명 23,417건은 다 있지만 효능/주의사항 텍스트(drugs_data, e약은요
    # 수집분)는 4,758건뿐이라 커버리지가 낮다. 결과가 아예 없거나(제품명 자체를 못 찾음), 있어도
    # 전부 내용이 비어있으면(제품은 찾았지만 효능/주의사항 데이터가 없는 경우) 식약처 공공데이터
    # API(e약은요)로 폴백한다.
    checked_public_api = False
    if not results or not any(_has_content(r) for r in results):
        if config.PUBLIC_DATA_API_KEY:
            checked_public_api = True
            summary_items = await medication_open_api_client.fetch_drug_summary(item_name=query)
            if not summary_items and stripped_query:
                summary_items = await medication_open_api_client.fetch_drug_summary(item_name=stripped_query)
            for item in summary_items:
                precaution_parts = [
                    item.get("atpnQesitm"),
                    item.get("atpnWarnQesitm"),
                    item.get("intrcQesitm"),
                ]
                precautions = " ".join(p.strip() for p in precaution_parts if p and p.strip())
                results.append(
                    _build_dur_result(
                        DrugProfile(
                            item_seq=str(item.get("itemSeq") or ""),
                            item_name=item.get("itemName") or query,
                            entp_name=item.get("entpName") or "",
                            efficacy=item.get("efcyQesitm"),
                            precautions=precautions,
                        )
                    )
                )

    results = _drop_empty_duplicates(results)

    # 결과가 끝까지 없으면, 어디까지 찾아봤는지를 그대로 알려준다 — "정보 없음"만 보여주면
    # 사용자가 "안 찾아본 것 아니냐"고 의심할 수 있어 신뢰도 문제가 생긴다.
    not_found_reason = None
    if not results:
        if checked_public_api:
            not_found_reason = (
                "MySQL 품목 마스터(식약처 DUR 데이터)와 식약처 공공데이터(e약은요) 모두에서 "
                "일치하는 의약품 정보를 찾지 못했습니다."
            )
        else:
            not_found_reason = (
                "MySQL 품목 마스터(식약처 DUR 데이터)에서 일치하는 의약품 정보를 찾지 못했습니다. "
                "공공데이터포털 실시간 조회는 서비스키가 설정되지 않아 시도하지 못했습니다."
            )

    end_time = time.perf_counter()
    elapsed_ms = (end_time - start_time) * 1000

    return {
        "elapsed_ms": round(elapsed_ms, 4),
        "results": results,
        "not_found_reason": not_found_reason,
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
    description=(
        "약품명 또는 외형 검색 fallback을 위한 검색창의 자동완성 API입니다. MySQL 캐시(Tier2)에"
        "더해 '더보기 > 약품 검색'(search-dur)이 참조하는 것과 같은 MySQL 품목 마스터"
        "(dur_prod_master_list)도 함께 조회해, 두 화면에서 같은 약이 서로 다르게 보이지 않도록 한다."
    ),
)
async def search_medications(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(..., min_length=1),
):
    service = MedicationService()
    return await service.search_medications(session, query)


@medication_router.post(
    "/recognition/jobs/{job_id}/confirm-for-family",
    response_model=RecognitionConfirmResult,
    summary="사용자 최종 확인 → 가족 구성원 몫으로 복약 스케줄 등록 (가족관리)",
    description=(
        "OCR로 인식한 처방전을 요청자 본인이 아니라, 요청자가 보호자로 등록된 가족 구성원 "
        "(target_profile_id) 몫으로 등록한다. 기존 /confirm과 별개 엔드포인트로 분리했다 - "
        "다른 조원이 확정등록 로직(마스터 DB 매칭 등)을 계속 다듬고 있어 병합 충돌을 피하기 "
        "위함(의도적 중복, 나중에 합칠지는 상의 후 결정)."
    ),
)
async def confirm_recognition_job_for_family(
    job_id: str,
    body: RecognitionConfirmForFamilyRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecognitionConfirmResult:
    service = MedicationService()
    return await service.confirm_recognition_job_for_family(
        session=session,
        job_id=job_id,
        requester_profile_id=profile.id,
        target_profile_id=body.target_profile_id,
        selected_candidate_drug_code=body.selected_candidate_drug_code,
        confirmed_fields=body.confirmed_fields,
    )


@medication_router.get(
    "/medications/family/{target_profile_id}",
    response_model=list[MedicationScheduleResponse],
    summary="가족 구성원의 복약 스케줄 전체 조회 (가족관리)",
    description="보호자가 자신이 관리하는 가족 구성원의 복약 스케줄 전체를 조회한다.",
)
async def list_medication_schedules_for_family(
    target_profile_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MedicationScheduleResponse]:
    service = MedicationService()
    return await service.list_schedules_for_family(session, profile.id, target_profile_id)


@medication_router.get(
    "/medications/interactions/family/{target_profile_id}",
    response_model=InteractionCheckResult,
    summary="가족 구성원의 병용금기 확인 (가족관리)",
)
async def check_interactions_for_family(
    target_profile_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InteractionCheckResult:
    service = MedicationService()
    return await service.check_interactions_for_family(session, profile.id, target_profile_id)


@medication_router.get(
    "/medications/food-interactions/family/{target_profile_id}",
    response_model=FoodInteractionCheckResult,
    summary="가족 구성원의 음식 상호작용 확인 (가족관리)",
)
async def check_food_interactions_for_family(
    target_profile_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FoodInteractionCheckResult:
    service = MedicationService()
    return await service.check_food_interactions_for_family(session, profile.id, target_profile_id)


@medication_router.delete(
    "/medications/{schedule_id}/for-family",
    status_code=204,
    summary="가족 구성원 몫 복약 스케줄 삭제 (가족관리)",
)
async def delete_medication_schedule_for_family(
    schedule_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = MedicationService()
    await service.delete_schedule_for_family(session, profile.id, schedule_id)
