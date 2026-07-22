from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MedicationSchedule(Base):
    """사용자가 등록한 복약 스케줄 테이블. profile_id 단위로 권한/조회를 제어한다.

    (T-MED-16) 예전에는 `medications`(자체 캐시 테이블)를 FK로 참조했으나, 원본 약품 마스터
    데이터가 이미 MySQL(`drugs_data`/`drug_identification`/`dur_prod_master_list` 등)에 전량
    적재되어 있어 그 캐시 계층을 없애고 `item_seq`를 직접 저장한다. `item_seq`는 저 테이블들에서
    row 단위 UNIQUE가 아니라서(같은 약의 시기별 외형/이미지 변형이 여러 행으로 존재) DB FK를 걸
    수 없다 - 존재 검증은 서비스 계층에서 한다(`MedicationRepository.item_seq_exists`).
    """

    __tablename__ = "medication_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    item_seq: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # 마스터 데이터에서 끝내 못 찾아 AUTO_ 더미(item_seq="AUTO_{hex10}")로 등록된 경우에만 채운다 -
    # 정상 item_seq는 이름을 마스터 데이터에서 조회하므로 항상 NULL로 둔다.
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    times: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # 복용 시간 목록 (e.g. ["08:30", "19:00"])
    source_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # 인식을 통해 등록된 경우 job_id 연계
    hospital_name: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 처방 병원명 (T-NTFY-2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MedicationDataCache(Base):
    """`medication_open_api_client.fetch_medication_master_data()`(낱알식별/허가정보/e약은요/DUR
    품목정보 4개 API 병렬 호출) 결과의 write-back 캐시. `app/models/drug_data_cache_model.py`의
    `DrugDataCache`(T-LLM-2-drug-gateway)와 동일한 패턴 — `query_name` 정확매치 키, 빈 응답은
    저장하지 않는다(나중에 API에 데이터가 채워질 수 있어 재시도 여지를 남긴다)."""

    __tablename__ = "medication_data_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    fields: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MedicationRecognitionJob(Base):
    """비동기 알약/처방전 OCR 분석 작업 기록 테이블."""

    __tablename__ = "medication_recognition_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID v4
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, processing, done, failed
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pill_photo, prescription, medical_record, medication_guide
    candidates: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True
    )  # 후보군 리스트 [{'drug_name': ..., 'match_rate': ..., 'drug_code': ...}]
    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 추출된 텍스트 필드 정보들
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
