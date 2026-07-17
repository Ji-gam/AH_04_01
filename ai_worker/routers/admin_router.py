import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, UploadFile

from ai_worker.core.logger import setup_logger
from ai_worker.ingest.manifest import SOURCE_DIR, load_manifest, scan_source_dir
from ai_worker.ingest.pipeline import build_vector_store, ingest_source, reset_collection
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
    build_paper_vector_store,
    reset_paper_collection,
    run_daily_pipeline,
)

logger = setup_logger("ai_worker.admin_router")

# T-ADMIN-1: 관리자 전용 인제스트 트리거. 브라우저에서 직접 닿지 않고 app/의 로그인 체크
# 통과 후에만 프록시되므로, 여기엔 자체 인증을 두지 않는다(app/apis/v1/admin_routers.py 참고).
admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _collection_count(db) -> int:
    return len(db.get(include=[])["ids"])


@admin_router.post(
    "/ingest/csv",
    response_model=IngestCsvResponse,
    summary="[관리자] CSV 업로드 후 DUR 인제스트 트리거",
    description="업로드한 파일을 source/에 저장하고, source/_manifest.yaml에 등록된 "
    "소스면 그 파일만 색인한다. 내용이 바뀐 문서만 재임베딩되고 원천에서 사라진 문서는 "
    "삭제된다(SQLRecordManager). 매니페스트에 없는 파일명이면 저장은 되지만 색인되지 "
    "않고 errors에 안내가 담긴다 — 등록하려면 매니페스트에 블록을 추가한다.",
)
async def upload_csv(file: Annotated[UploadFile, File(...)]) -> IngestCsvResponse:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "upload.csv"
    (SOURCE_DIR / filename).write_bytes(await file.read())

    spec = next((s for s in load_manifest() if s.file == filename and s.rag), None)
    if spec is None:
        return IngestCsvResponse(
            filename=filename,
            deleted=0,
            ingested=0,
            collection_count=0,
            errors=[f"{filename}은(는) source/_manifest.yaml에 RAG 소스로 등록되지 않았습니다. 파일은 저장했습니다."],
        )

    result = await asyncio.to_thread(ingest_source, spec)
    return IngestCsvResponse(
        filename=filename,
        deleted=result["num_deleted"],
        ingested=result["num_added"] + result["num_updated"],
        collection_count=_collection_count(build_vector_store(spec.collection)),
        errors=[],
    )


@admin_router.post(
    "/ingest/csv/reset",
    summary="[관리자] dur_rules 컬렉션 삭제(재색인 준비)",
    description="컬렉션과 인제스트 장부를 함께 비운다. 장부를 남기면 재색인이 조용히 스킵된다.",
)
async def reset_dur() -> dict[str, str]:
    await asyncio.to_thread(reset_collection, "dur_rules")
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
    summary="[관리자] pubmed_papers 컬렉션 삭제(재색인 준비)",
    description="reset_paper_collection()을 호출해 기존 컬렉션을 통째로 삭제한다.",
)
async def reset_papers() -> dict[str, str]:
    reset_paper_collection()
    return {"status": "reset"}


@admin_router.get(
    "/ingest/status",
    response_model=IngestStatusResponse,
    summary="[관리자] 인제스트 현황 조회",
    description="dur_rules/pubmed_papers 컬렉션 문서 수와 질환별 원본 PubMed JSON 파일 건수를 반환한다.",
)
async def ingest_status() -> IngestStatusResponse:
    dur_count = _collection_count(build_vector_store("dur_rules"))
    paper_count = _collection_count(build_paper_vector_store())

    papers_raw_counts: dict[str, int] = {}
    for disease in SUPPORTED_DISEASES:
        path = RAW_DATA_DIR / f"{disease}.json"
        papers_raw_counts[disease] = len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0

    return IngestStatusResponse(
        dur_rules_count=dur_count,
        pubmed_papers_count=paper_count,
        papers_raw_counts=papers_raw_counts,
        sources=SourceScanResult(**scan_source_dir(load_manifest())),
    )
