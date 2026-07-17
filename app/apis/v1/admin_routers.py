from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_request_user
from app.dtos.admin import (
    AdminChatSessionListItem,
    IngestCsvResult,
    IngestPapersRequest,
    IngestPapersResult,
    IngestStatusResult,
)
from app.dtos.chat import ChatMessageResponse
from app.repositories.chat_repository import ChatRepository
from app.services.ai_worker_gateway import AIWorkerGateway

admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_request_user)])


@admin_router.get(
    "/chat/sessions",
    response_model=list[AdminChatSessionListItem],
    summary="[관리자] 전체 채팅 세션 목록 조회",
    description="모든 프로필의 채팅 세션을 최신순으로 조회한다(모니터링 목적, profile 스코핑 없음).",
)
async def list_all_chat_sessions(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[AdminChatSessionListItem]:
    rows = await ChatRepository().list_all_sessions(session, limit=limit, offset=offset)
    return [
        AdminChatSessionListItem(
            id=chat_session.id,
            profile_id=chat_session.profile_id,
            profile_name=profile_name,
            created_at=chat_session.created_at,
        )
        for chat_session, profile_name in rows
    ]


@admin_router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    summary="[관리자] 채팅 세션 상세 메시지 조회",
    description="특정 세션의 메시지를 시간순으로 조회한다(출처의 RAG 유사도 score 포함, profile 소유권 체크 없음).",
    responses={404: {"description": "세션이 존재하지 않음"}},
)
async def get_admin_chat_session_messages(
    session_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatMessageResponse]:
    chat_session = await ChatRepository().get_session(session, session_id)
    if chat_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="채팅 세션을 찾을 수 없습니다.")

    messages = await ChatRepository().list_messages(session, session_id, limit=200)
    return [
        ChatMessageResponse(role=m.role.value.lower(), content=m.content, sources=m.sources, created_at=m.created_at)
        for m in messages
    ]


@admin_router.post(
    "/rag/ingest/csv",
    response_model=IngestCsvResult,
    summary="[관리자] CSV 업로드 후 DUR 인제스트 트리거",
    description="업로드한 CSV를 ai_worker에 전달해 dur_rules 컬렉션에 그 파일 소스만 "
    "upsert한다(재업로드=최신 스냅샷으로 자동 갱신). 컬렉션 전체 리셋은 "
    "POST /admin/rag/ingest/csv/reset을 쓴다.",
)
async def upload_rag_csv(file: Annotated[UploadFile, File(...)]) -> IngestCsvResult:
    file_bytes = await file.read()
    result = await AIWorkerGateway().upload_csv(file_bytes, file.filename or "upload.csv")
    return IngestCsvResult(**result)


@admin_router.post(
    "/rag/ingest/csv/reset",
    summary="[관리자] dur_rules 컬렉션 삭제(재색인 준비)",
)
async def reset_rag_dur_collection() -> dict:
    return await AIWorkerGateway().reset_dur_collection()


@admin_router.post(
    "/rag/ingest/papers",
    response_model=IngestPapersResult,
    summary="[관리자] 논문(PubMed) 인제스트 파이프라인 트리거",
    description="ai_worker의 인제스트 파이프라인을 백그라운드로 실행하도록 트리거한다(즉시 반환).",
)
async def trigger_rag_paper_ingest(body: IngestPapersRequest) -> IngestPapersResult:
    result = await AIWorkerGateway().trigger_paper_ingest(body.categories, body.retmax_per_category)
    return IngestPapersResult(**result)


@admin_router.post(
    "/rag/ingest/papers/reset",
    summary="[관리자] pubmed_papers 컬렉션 삭제(재색인 준비)",
)
async def reset_rag_paper_collection() -> dict:
    return await AIWorkerGateway().reset_paper_collection()


@admin_router.get(
    "/rag/ingest/status",
    response_model=IngestStatusResult,
    summary="[관리자] 인제스트 현황 조회",
    description="dur_rules/pubmed_papers 컬렉션 문서 수와 질환별 원본 PubMed JSON 파일 건수를 반환한다.",
)
async def get_rag_ingest_status() -> IngestStatusResult:
    result = await AIWorkerGateway().ingest_status()
    return IngestStatusResult(**result)
