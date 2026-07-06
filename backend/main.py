import sys
import os
import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from backend.core.config import settings
from backend.core.database import engine, Base, SessionLocal

# 경로 설정
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------
# 모델 임포트 (Base.metadata.create_all이 모든 테이블을 인식하려면 전부 임포트되어 있어야 함)
# ------------------------------------------------------------------
from backend.domains.user.model import User
from backend.domains.emergency_card.model import EmergencyCard
from backend.domains.pwa_subscription.model import PwaSubscription
from backend.domains.support_group.model import SupportGroup, GroupMember
from backend.domains.medication.model import Medication
from backend.domains.record.model import MedicalRecord, RecordMedicationMapping, OcrTask
from backend.domains.schedule.model import MedicationSchedule
from backend.domains.intake_log.model import IntakeLog
from backend.domains.food_intake.model import FoodIntakeLog
from backend.domains.drug_food_interaction.model import DrugFoodInteraction
from backend.domains.health_metric.model import HealthMetric
from backend.domains.appointment.model import Appointment
from backend.domains.symptom_log.model import SymptomLog
from backend.domains.chat.model import ChatSession, ChatMessage
from backend.domains.generated_guide.model import GeneratedGuide

# ------------------------------------------------------------------
# 라우터 임포트
# ------------------------------------------------------------------
from backend.domains.auth import router as auth_routers
from backend.domains.user import router as user_routers
from backend.domains.emergency_card import router as emergency_card_routers
from backend.domains.pwa_subscription import router as pwa_subscription_routers
from backend.domains.support_group import router as support_group_routers
from backend.domains.medication import router as medication_routers
from backend.domains.record import router as record_routers
from backend.domains.schedule import router as schedule_routers
from backend.domains.intake_log import router as intake_log_routers
from backend.domains.food_intake import router as food_intake_routers
from backend.domains.drug_food_interaction import router as drug_food_interaction_routers
from backend.domains.health_metric import router as health_metric_routers
from backend.domains.appointment import router as appointment_routers
from backend.domains.symptom_log import router as symptom_log_routers
from backend.domains.chat import router as chat_routers
from backend.domains.generated_guide import router as generated_guide_routers
from backend.domains.drug import router as drug_test_router  # v3 명세엔 없는 사내 테스트용 툴 (MFDS 연동 확인용)


# 1. Lifespan 설정 (서버 시작/종료 시 작업 관리)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"DEBUG: Engine URL: {engine.url}")
    if engine.dialect.name == "sqlite":
        print("경고: SQLite에 연결되었습니다. .env 설정을 확인하세요!")

    inspector = inspect(engine)
    if not inspector.has_table("users"):
        print("테이블을 생성합니다...")
        Base.metadata.create_all(bind=engine)

        # Mock Data 초기화 (v3 명세 필드 기준)
        db = SessionLocal()
        try:
            from backend.utils.security import get_password_hash

            user = User(
                email="hong@gmail.com",
                password_hash=get_password_hash("hashed_pw_here"),
                name="홍길동",
                role_type="PATIENT",
                gender="MALE",
                birth_date="1955-08-15",
                sns_provider="LOCAL",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            medication = Medication(medication_name="삭센다펜주", form_type="INJECTION", dosage_guideline="1일 1회 자가 주사")
            db.add(medication)
            db.commit()
            db.refresh(medication)

            record = MedicalRecord(
                user_id=user.id, document_type="PRESCRIPTION",
                visit_date=datetime.date(2026, 6, 1),
                hospital_name="서울중앙병원", department_name="내과", diagnosis_name="고혈압",
            )
            db.add(record)
            db.commit()
            db.refresh(record)

            mapping = RecordMedicationMapping(
                record_id=record.id, medication_id=medication.id,
                dosage_per_take="1정", takes_per_day=1, duration_days=30,
                device_type="TABLET", total_prescribed_quantity=30, remaining_quantity=30,
            )
            db.add(mapping)
            db.commit()

            print("Successfully populated mock data!")
        finally:
            db.close()
    else:
        print("Database already exists, skipping creation.")

    yield


# 2. FastAPI 앱 생성
app = FastAPI(
    title="ReMedi API (API_Specification_v3 기준)",
    description="LLM 기반 개인 맞춤형 복약 안내 및 헬스케어 서비스",
    lifespan=lifespan,
)

# 3. CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print(f"DEBUG: API Key loaded: {'Success' if settings.MFDS_API_KEY else 'Failed'}")

# ------------------------------------------------------------------
# 4. 라우터 연결 (v3 명세 기준 /api/v1 프리픽스)
# ------------------------------------------------------------------
API_V1 = "/api/v1"

app.include_router(auth_routers.router, prefix=f"{API_V1}/users", tags=["[M1] 회원 및 계정 관리 - Auth"])
app.include_router(user_routers.router, prefix=f"{API_V1}/users", tags=["[M1] 회원 및 계정 관리 - User"])
app.include_router(pwa_subscription_routers.router, prefix=f"{API_V1}/pwa-subscriptions", tags=["[M2] PWA 푸시 구독 관리"])
app.include_router(support_group_routers.router, prefix=f"{API_V1}/support-groups", tags=["[M3] 서포트 그룹 및 경쟁 관리"])
app.include_router(emergency_card_routers.router, prefix=f"{API_V1}/emergency-cards", tags=["[M4] 응급 의료 카드"])
app.include_router(record_routers.router, prefix=f"{API_V1}/medical-records", tags=["[M5] 진료 기록 및 처방약 관리"])
app.include_router(medication_routers.router, prefix=f"{API_V1}/medications", tags=["[M5] 의약품 마스터"])
app.include_router(schedule_routers.router, prefix=f"{API_V1}/medication-schedules", tags=["[M6] 복약 일정 및 수행 이력 - Schedule"])
app.include_router(intake_log_routers.router, prefix=f"{API_V1}/intake-logs", tags=["[M6] 복약 일정 및 수행 이력 - Intake Log"])
app.include_router(food_intake_routers.router, prefix=f"{API_V1}/food-intake-logs", tags=["[M7] 식사 이력 관리"])
app.include_router(drug_food_interaction_routers.router, prefix=f"{API_V1}/drug-food-interactions", tags=["[M8] 약물-음식 상호작용 규칙"])
app.include_router(health_metric_routers.router, prefix=f"{API_V1}/health-metrics", tags=["[M9] 건강 추적, 증상 및 병원 관리 - Health Metric"])
app.include_router(appointment_routers.router, prefix=f"{API_V1}/appointments", tags=["[M9] 건강 추적, 증상 및 병원 관리 - Appointment"])
app.include_router(symptom_log_routers.router, prefix=f"{API_V1}/symptom-logs", tags=["[M9] 건강 추적, 증상 및 병원 관리 - Symptom Log"])
app.include_router(chat_routers.router, prefix=f"{API_V1}/chat", tags=["[M10] AI 챗봇 및 가이드 - Chat"])
app.include_router(generated_guide_routers.router, prefix=f"{API_V1}/generated-guides", tags=["[M10] AI 챗봇 및 가이드 - Generated Guide"])

# v3 명세에는 없는 사내 테스트용 툴 (MFDS Open API 연동 확인용, 버저닝 대상 아님)
app.include_router(drug_test_router.router, prefix="/api/test", tags=["[사내 테스트용] 의약품 정보 조회"])


@app.get("/")
def read_root():
    return {"message": "ReMedi Backend is running (API_Specification_v3 기준)"}
