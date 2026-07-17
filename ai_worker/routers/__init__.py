from fastapi import APIRouter

from ai_worker.routers.admin_router import admin_router
from ai_worker.routers.chat_agent_router import chat_agent_router
from ai_worker.routers.generation_router import generation_router
from ai_worker.routers.health_router import health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(generation_router)
api_router.include_router(chat_agent_router)
api_router.include_router(admin_router)
