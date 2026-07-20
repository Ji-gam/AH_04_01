from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication_model import Medication, MedicationRecognitionJob, MedicationSchedule


class MedicationRepository:
    async def get_medication_by_id(self, session: AsyncSession, med_id: int) -> Medication | None:
        result = await session.execute(select(Medication).where(Medication.id == med_id))
        return result.scalar_one_or_none()

    async def get_medication_by_code(self, session: AsyncSession, code: str) -> Medication | None:
        result = await session.execute(select(Medication).where(Medication.standard_code == code))
        return result.scalar_one_or_none()

    async def search_medication_by_name(self, session: AsyncSession, name: str) -> list[Medication]:
        result = await session.execute(select(Medication).where(Medication.medication_name.like(f"%{name}%")).limit(10))
        return list(result.scalars().all())

    async def list_medication_names(self, session: AsyncSession, limit: int) -> list[tuple[int, str]]:
        """(#106) OCR 글자 오인식(예: "패취"→"매취") 구제를 위한 유사도 매칭에서, 마스터 DB
        약품명 전체와 비교할 (id, 이름) 목록을 가져온다. 비교 비용을 억제하기 위해 상한을 둔다."""
        result = await session.execute(select(Medication.id, Medication.medication_name).limit(limit))
        return [(row.id, row.medication_name) for row in result.all()]

    async def search_medications_by_appearance(
        self, session: AsyncSession, shape: str | None, color: str | None, letters: str | None
    ) -> list[Medication]:
        query = select(Medication)
        if shape:
            query = query.where(Medication.shape == shape)
        if color:
            query = query.where(Medication.color == color)
        if letters:
            query = query.where(Medication.letters.like(f"%{letters}%"))
        result = await session.execute(query.limit(10))
        return list(result.scalars().all())

    async def create_medication(self, session: AsyncSession, medication: Medication) -> Medication:
        session.add(medication)
        await session.commit()
        await session.refresh(medication)
        return medication

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
