from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.medication_model import Medication, MedicationSchedule, MedicationRecognitionJob


class MedicationRepository:
    async def get_medication_by_id(self, session: AsyncSession, med_id: int) -> Medication | None:
        result = await session.execute(select(Medication).where(Medication.id == med_id))
        return result.scalar_one_or_none()

    async def get_medication_by_code(self, session: AsyncSession, code: str) -> Medication | None:
        result = await session.execute(select(Medication).where(Medication.standard_code == code))
        return result.scalar_one_or_none()

    async def search_medication_by_name(self, session: AsyncSession, name: str) -> list[Medication]:
        result = await session.execute(
            select(Medication).where(Medication.medication_name.like(f"%{name}%")).limit(10)
        )
        return list(result.scalars().all())

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
            select(MedicationSchedule).where(MedicationSchedule.profile_id == profile_id)
        )
        return list(result.scalars().all())

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
