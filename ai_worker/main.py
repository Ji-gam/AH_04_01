from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_worker.core.logger import setup_logger
from ai_worker.routers import api_router
from ai_worker.services.retrieve_service import db_holder, initialize_rag  # noqa: F401 (테스트 주입 지점 재노출)

logger = setup_logger("ai_worker.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_rag()
    yield


app = FastAPI(
    title="ReMedi AI Worker Service",
    description="RAG 파이프라인 및 Vector DB 검색 서비스를 제공하는 백그라운드 워커 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
