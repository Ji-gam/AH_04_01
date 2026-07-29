from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dur import DrugIdentification, DrugMaster, DurProdMasterList
from app.models.medication_model import MedicationDataCache, MedicationRecognitionJob, MedicationSchedule


class MedicationRepository:
    async def item_seq_exists(self, session: AsyncSession, item_seq: str) -> bool:
        """(T-MED-16) `medication_schedules.item_seq`는 DB FK가 없으므로(마스터 데이터에서
        item_seq가 row 단위 UNIQUE가 아님) 여기서 앱 레벨로 존재만 확인한다. `dur_prod_master_list`
        (검색/매칭이 실제로 기준으로 삼는 품목 마스터, 가장 넓은 커버리지) 또는 `drugs_data`/
        `drug_identification` 어느 한쪽에라도 있으면 유효한 것으로 본다."""
        result = await session.execute(
            select(DurProdMasterList.id).where(DurProdMasterList.item_seq == item_seq).limit(1)
        )
        if result.first() is not None:
            return True
        result = await session.execute(select(DrugMaster.id).where(DrugMaster.item_seq == item_seq).limit(1))
        if result.first() is not None:
            return True
        result = await session.execute(
            select(DrugIdentification.id).where(DrugIdentification.item_seq == item_seq).limit(1)
        )
        return result.first() is not None

    async def find_item_seq_by_exact_name(self, session: AsyncSession, item_name: str) -> str | None:
        """(#PLAVIX-MATCH-GAP) `DurDrugRepository.search_item_names`의 Tier1 검색은
        `dur_prod_master_list` 한 곳만 보는데, 이 테이블엔 없지만 `drugs_data`/
        `drug_identification`엔 이미 있는 약이 있다(세 마스터 테이블 커버리지가 서로 다름 -
        예: "플라빅스정75밀리그램(...)"은 `drug_identification`에만 있음). Tier1이 놓친 이름을
        Tier3 실시간 공공 API로 넘기기 전에, 이미 로컬에 있는 다른 두 마스터 테이블에서 정확
        일치를 한 번 더 확인해 불필요한 API 호출과 매번 다른 item_seq 재발급을 줄인다."""
        result = await session.execute(select(DrugMaster.item_seq).where(DrugMaster.item_name == item_name).limit(1))
        row = result.first()
        if row is not None:
            return row[0]
        result = await session.execute(
            select(DrugIdentification.item_seq).where(DrugIdentification.item_name == item_name).limit(1)
        )
        row = result.first()
        return row[0] if row is not None else None

    async def create_schedule(self, session: AsyncSession, schedule: MedicationSchedule) -> MedicationSchedule:
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)
        return schedule

    async def list_schedules_by_profile(self, session: AsyncSession, profile_id: int) -> list[MedicationSchedule]:
        result = await session.execute(
            select(MedicationSchedule)
            .where(MedicationSchedule.profile_id == profile_id)
            .order_by(MedicationSchedule.id.asc())
        )
        return list(result.scalars().all())

    async def get_schedule_by_id(self, session: AsyncSession, schedule_id: int) -> MedicationSchedule | None:
        result = await session.execute(select(MedicationSchedule).where(MedicationSchedule.id == schedule_id))
        return result.scalar_one_or_none()

    async def delete_schedule(self, session: AsyncSession, schedule: MedicationSchedule) -> None:
        await session.delete(schedule)
        await session.commit()

    async def create_recognition_job(
        self, session: AsyncSession, job: MedicationRecognitionJob
    ) -> MedicationRecognitionJob:
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    async def get_recognition_job(self, session: AsyncSession, job_id: str) -> MedicationRecognitionJob | None:
        result = await session.execute(select(MedicationRecognitionJob).where(MedicationRecognitionJob.id == job_id))
        return result.scalar_one_or_none()

    async def update_recognition_job(
        self,
        session: AsyncSession,
        job_id: str,
        status: str,
        candidates: list[dict] | None = None,
        extracted_fields: dict | None = None,
    ) -> MedicationRecognitionJob | None:
        job = await self.get_recognition_job(session, job_id)
        if job:
            job.status = status
            if candidates is not None:
                job.candidates = candidates
            if extracted_fields is not None:
                job.extracted_fields = extracted_fields
            await session.commit()
            await session.refresh(job)
        return job

    async def set_recognition_job_image(
        self,
        session: AsyncSession,
        job_id: str,
        image_storage_key: str,
        image_mime_type: str,
        image_size_bytes: int,
    ) -> None:
        """(REQ-DOC-003) OCR 인식과 별개로, 암호화 저장이 성공한 직후 job 행에 이미지
        포인터만 기록한다. 저장이 스킵된 경우(FIELD_ENCRYPTION_KEY 미설정)는 호출 자체가
        안 되므로 image_storage_key는 None으로 남는다."""
        job = await self.get_recognition_job(session, job_id)
        if job:
            job.image_storage_key = image_storage_key
            job.image_mime_type = image_mime_type
            job.image_size_bytes = image_size_bytes
            await session.commit()

    async def list_recognition_jobs_by_profile(
        self, session: AsyncSession, profile_id: int, source_type: str | None = None
    ) -> list[MedicationRecognitionJob]:
        """(REQ-DOC-003) "내 문서함" 목록 - 최신순. 날짜별 그룹핑은 프론트에서 created_at
        기준으로 한다."""
        stmt = select(MedicationRecognitionJob).where(MedicationRecognitionJob.profile_id == profile_id)
        if source_type is not None:
            stmt = stmt.where(MedicationRecognitionJob.source_type == source_type)
        stmt = stmt.order_by(MedicationRecognitionJob.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def clear_recognition_job_document(self, session: AsyncSession, job: MedicationRecognitionJob) -> None:
        """(REQ-DOC-003) "원본+추출데이터 완전삭제" - job 행 자체는 MedicationSchedule.
        source_job_id 참조 무결성 때문에 지우지 않고, 민감한 페이로드만 비운다. 파일 삭제는
        호출부(서비스 계층)가 이 메서드를 부르기 전에 이미 처리한다."""
        job.image_storage_key = None
        job.image_mime_type = None
        job.image_size_bytes = None
        job.image_deleted_at = func.now()
        job.candidates = []
        job.extracted_fields = {}
        await session.commit()
        await session.refresh(job)

    async def get_cached_master_data(self, session: AsyncSession, query_name: str) -> dict | None:
        """`medication_open_api_client.fetch_medication_master_data()` write-back 캐시 조회
        (T-LLM-2-drug-gateway `DrugDataCache`와 동일 패턴 — query_name 정확매치)."""
        result = await session.execute(select(MedicationDataCache).where(MedicationDataCache.query_name == query_name))
        cached = result.scalar_one_or_none()
        return cached.fields if cached else None

    async def write_back_master_data(self, session: AsyncSession, query_name: str, fields: dict) -> None:
        """캐시 쓰기는 best-effort다 — 실패해도 이미 계산된 응답 회신을 막지 않는다."""
        try:
            session.add(MedicationDataCache(query_name=query_name, fields=fields))
            await session.commit()
        except Exception:
            await session.rollback()
