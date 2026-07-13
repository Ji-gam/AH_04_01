from fastapi import APIRouter

from ai_worker.routers.generation_router import generation_router
from ai_worker.routers.paper_agent_router import paper_agent_router
from ai_worker.routers.retrieve_router import retrieve_router

api_router = APIRouter()
api_router.include_router(retrieve_router)
api_router.include_router(generation_router)
api_router.include_router(paper_agent_router)
