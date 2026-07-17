import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from ai_worker.core.logger import setup_logger
from ai_worker.ingest.pipeline import build_vector_store, ingest_source, reset_collection, scan
from ai_worker.ingest.sources import SOURCE_DIR, STRUCTURED, UNSTRUCTURED, discover, nfc
from ai_worker.schemas.admin_schema import (
    IngestCsvResponse,
    IngestPapersRequest,
    IngestPapersStartedResponse,
    IngestStatusResponse,
    SourceScanResult,
)
from ai_worker.tasks.ingest_papers import (
    RAW_DATA_DIR,
    SUPPORTED_DISEASES,
    run_daily_pipeline,
)

DUR_COLLECTION = STRUCTURED
PAPER_COLLECTION = UNSTRUCTURED

logger = setup_logger("ai_worker.admin_router")

# T-ADMIN-1: 관리자 전용 인제스트 트리거. 브라우저에서 직접 닿지 않고 app/의 로그인 체크
# 통과 후에만 프록시되므로, 여기엔 자체 인증을 두지 않는다(app/apis/v1/admin_routers.py 참고).
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _collection_count(db) -> int:
    return len(db.get(include=[])["ids"])


@admin_router.post(
    "/ingest/csv",
    response_model=IngestCsvResponse,
    summary="[관리자] 파일 업로드 후 색인",
    description="업로드한 파일을 드롭 폴더(source/)에 저장하고 바로 색인한다. **설정 파일을 "
    "고칠 필요가 없다** — 폴더에 있으면 색인 대상이다. 로더는 확장자가 정하므로 읽을 줄 아는 "
    "형식(.csv/.json/.md/.pdf)이어야 한다. 내용이 바뀐 문서만 재임베딩되고 원천에서 사라진 "
    "행은 삭제된다(SQLRecordManager).",
)
async def upload_csv(file: Annotated[UploadFile, File(...)]) -> IngestCsvResponse:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    # macOS에서 온 한글 파일명은 NFD일 수 있다. 저장 시점에 NFC로 맞춰야 아래 discover()의
    # 이름 비교가 어긋나지 않는다(sources.nfc 참고).
    filename = nfc(file.filename or "upload.csv")
    (SOURCE_DIR / filename).write_bytes(await file.read())

    source = next((s for s in discover() if s.name == filename), None)
    if source is None:
        # `_`나 `.`로 시작하는 이름은 설정·파생물로 취급해 드롭 폴더 스캔에서 빠진다.
        return IngestCsvResponse(
            filename=filename,
            deleted=0,
            ingested=0,
            collection_count=0,
            errors=[f"{filename}은(는) 저장했지만 색인 대상이 아닙니다(이름이 `_`나 `.`로 시작)."],
        )

    try:
        result = await asyncio.to_thread(ingest_source, source)
    except Exception as e:
        # 지원 안 하는 확장자, 0건 로드 등. 저장은 됐으므로 파일명과 함께 이유를 돌려준다.
        logger.error(f"{filename} 색인 실패: {e}")
        return IngestCsvResponse(filename=filename, deleted=0, ingested=0, collection_count=0, errors=[str(e)])

    return IngestCsvResponse(
        filename=filename,
        deleted=result["num_deleted"],
        ingested=result["num_added"] + result["num_updated"],
        collection_count=_collection_count(build_vector_store(source.collection)),
        errors=[],
    )


@admin_router.post(
    "/ingest/csv/reset",
    summary="[관리자] structured 컬렉션(CSV) 삭제(재색인 준비)",
    description="컬렉션과 인제스트 장부를 함께 비운다. 장부를 남기면 재색인이 조용히 스킵된다.",
)
async def reset_dur() -> dict[str, str]:
    await asyncio.to_thread(reset_collection, DUR_COLLECTION)
    return {"status": "reset"}


@admin_router.post(
    "/ingest/papers",
    response_model=IngestPapersStartedResponse,
    summary="[관리자] 논문(PubMed) 인제스트 파이프라인 트리거",
    description="run_daily_pipeline()을 백그라운드로 실행한다(1분 이상 걸릴 수 있어 즉시 반환). "
    "완료 후 결과는 /admin/ingest/status로 확인한다.",
)
async def trigger_paper_ingest(
    body: IngestPapersRequest, background_tasks: BackgroundTasks
) -> IngestPapersStartedResponse:
    async def _run() -> None:
        try:
            await run_daily_pipeline(retmax_per_category=body.retmax_per_category or 50, categories=body.categories)
        except Exception as e:
            logger.error(f"논문 인제스트 백그라운드 실행 실패: {e}")

    background_tasks.add_task(_run)
    return IngestPapersStartedResponse()


@admin_router.post(
    "/ingest/papers/reset",
    summary="[관리자] unstructured 컬렉션(논문/안내서) 삭제(재색인 준비)",
    description="컬렉션과 인제스트 장부를 함께 비운다. 장부를 남기면 재색인이 조용히 스킵된다.",
)
async def reset_papers() -> dict[str, str]:
    await asyncio.to_thread(reset_collection, PAPER_COLLECTION)
    return {"status": "reset"}


@admin_router.get(
    "/ingest/status",
    response_model=IngestStatusResponse,
    summary="[관리자] 인제스트 현황 조회",
    description="structured/unstructured 컬렉션 문서 수와 질환별 원본 PubMed JSON 파일 건수를 반환한다.",
)
async def ingest_status() -> IngestStatusResponse:
    dur_count = _collection_count(build_vector_store(DUR_COLLECTION))
    paper_count = _collection_count(build_vector_store(PAPER_COLLECTION))

    papers_raw_counts: dict[str, int] = {}
    for disease in SUPPORTED_DISEASES:
        path = RAW_DATA_DIR / f"{disease}.json"
        papers_raw_counts[disease] = len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0

    return IngestStatusResponse(
        structured_count=dur_count,
        unstructured_count=paper_count,
        papers_raw_counts=papers_raw_counts,
        sources=SourceScanResult(**scan()),
    )
