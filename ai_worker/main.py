import logging

from fastapi import FastAPI

from ai_worker.routers import api_router
from ai_worker.services.retrieve_service import db_holder, initialize_rag  # noqa: F401 (테스트 주입 지점 재노출)

# 로거 설정
logger = logging.getLogger("ai_worker.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ReMedi AI Worker Service",
    description="RAG 파이프라인 및 Vector DB 검색 서비스를 제공하는 백그라운드 워커 API",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    initialize_rag()


app.include_router(api_router)
