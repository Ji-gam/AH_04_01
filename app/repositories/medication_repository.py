from sqlalchemy import select
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
