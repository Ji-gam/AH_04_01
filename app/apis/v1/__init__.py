from fastapi import APIRouter

from app.apis.v1.auth_routers import auth_router
from app.apis.v1.chat_routers import chat_router
from app.apis.v1.content_routers import content_router
from app.apis.v1.diary_routers import diary_router
from app.apis.v1.diet_routers import diet_router
from app.apis.v1.disease_routers import disease_router
from app.apis.v1.dur import dur_router
from app.apis.v1.exercise_routers import exercise_router
from app.apis.v1.family_routers import family_router
from app.apis.v1.goal_routers import goal_router
from app.apis.v1.habit_routers import habit_router
from app.apis.v1.medication import medication_router
from app.apis.v1.medication_intake_routers import intake_router
from app.apis.v1.notice_routers import notice_router
from app.apis.v1.notification_log_routers import notification_log_router
from app.apis.v1.notification_routers import notification_router
from app.apis.v1.notification_settings_routers import notification_settings_router
from app.apis.v1.push_routers import push_router
from app.apis.v1.user_routers import user_router
from app.apis.v1.weekly_report_routers import weekly_report_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(chat_router)
v1_routers.include_router(content_router)
v1_routers.include_router(diary_router)
v1_routers.include_router(medication_router)
v1_routers.include_router(notification_router)
v1_routers.include_router(notification_log_router)
v1_routers.include_router(notification_settings_router)
v1_routers.include_router(notice_router)
v1_routers.include_router(push_router)
v1_routers.include_router(disease_router)
v1_routers.include_router(habit_router)
v1_routers.include_router(dur_router)
v1_routers.include_router(family_router)
v1_routers.include_router(goal_router)
v1_routers.include_router(intake_router)
v1_routers.include_router(diet_router)
v1_routers.include_router(exercise_router)
v1_routers.include_router(weekly_report_router)
