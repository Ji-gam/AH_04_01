from fastapi import APIRouter

from app.apis.v1.appointment import appointment_router
from app.apis.v1.auth_routers import auth_router
from app.apis.v1.chat import chat_router
from app.apis.v1.drug_interaction import drug_interaction_router
from app.apis.v1.emergency_card import emergency_card_router
from app.apis.v1.food_intake import food_intake_router
from app.apis.v1.generated_guide import generated_guide_router
from app.apis.v1.health_metric import health_metric_router
from app.apis.v1.medication import medication_router
from app.apis.v1.pwa_subscription import pwa_subscription_router
from app.apis.v1.record import record_router
from app.apis.v1.schedule import schedule_router
from app.apis.v1.support_group import support_group_router
from app.apis.v1.symptom_log import symptom_log_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(medication_router)
v1_routers.include_router(schedule_router)
v1_routers.include_router(record_router)
v1_routers.include_router(chat_router)
v1_routers.include_router(support_group_router)
v1_routers.include_router(health_metric_router)
v1_routers.include_router(symptom_log_router)
v1_routers.include_router(food_intake_router)
v1_routers.include_router(emergency_card_router)
v1_routers.include_router(drug_interaction_router)
v1_routers.include_router(pwa_subscription_router)
v1_routers.include_router(appointment_router)
v1_routers.include_router(generated_guide_router)
