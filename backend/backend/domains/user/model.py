# backend/domains/user/model.py
# API_Specification_v3.pdf [M1] USERS 테이블 기준
import datetime
from sqlalchemy import Column, Integer, String, Boolean, Time, DateTime, Date
from sqlalchemy.orm import relationship
from backend.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # sns 로그인 유저는 null 가능
    name = Column(String(50), nullable=False)
    role_type = Column(String(20), nullable=False, default="PATIENT")  # PATIENT / GUARDIAN
    gender = Column(String(10), nullable=True)
    birth_date = Column(String(20), nullable=True)

    # 소셜 로그인
    sns_provider = Column(String(20), nullable=False, default="LOCAL")  # LOCAL / GOOGLE
    sns_id = Column(String(255), nullable=True)

    # JWT Refresh Token (DB 동기화용 - v3 명세 M1)
    refresh_token = Column(String(500), nullable=True)

    # 노인 접근성 개인화 설정
    use_voice_mode = Column(Boolean, default=False)
    use_large_font = Column(Boolean, default=False)
    wake_time = Column(Time, nullable=True)
    breakfast_time = Column(Time, nullable=True)
    lunch_time = Column(Time, nullable=True)
    dinner_time = Column(Time, nullable=True)
    bed_time = Column(Time, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 (다른 도메인에서 back_populates로 짝을 맞춰줘야 함 - 안 맞으면 서버 전체가 죽으니 주의!)
    emergency_card = relationship("EmergencyCard", back_populates="user", uselist=False, cascade="all, delete-orphan")
    medical_records = relationship("MedicalRecord", back_populates="user", cascade="all, delete-orphan")
    generated_guides = relationship("GeneratedGuide", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    medication_schedules = relationship("MedicationSchedule", back_populates="user", cascade="all, delete-orphan")
    food_intake_logs = relationship("FoodIntakeLog", back_populates="user", cascade="all, delete-orphan")
    health_metrics = relationship("HealthMetric", back_populates="user", cascade="all, delete-orphan")
    symptom_logs = relationship("SymptomLog", back_populates="user", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="user", cascade="all, delete-orphan")
    pwa_subscriptions = relationship("PwaSubscription", back_populates="user", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
