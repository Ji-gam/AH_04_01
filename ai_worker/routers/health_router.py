from fastapi import APIRouter

from ai_worker.services.retrieve_service import db_holder

health_router = APIRouter()


@health_router.get("/health")
async def health_check():
    """컨테이너 헬스체크용 엔드포인트."""
    return {"status": "healthy", "db_loaded": db_holder["db"] is not None}
