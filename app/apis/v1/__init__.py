from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.chat_routers import chat_router
from app.apis.v1.content_routers import content_router
from app.apis.v1.disease_routers import disease_router
from app.apis.v1.dur import dur_router
from app.apis.v1.habit_routers import habit_router
from app.apis.v1.medication import medication_router
from app.apis.v1.notification_routers import notification_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(chat_router)
v1_routers.include_router(content_router)
v1_routers.include_router(medication_router)
v1_routers.include_router(notification_router)
v1_routers.include_router(disease_router)
v1_routers.include_router(habit_router)
v1_routers.include_router(dur_router)
