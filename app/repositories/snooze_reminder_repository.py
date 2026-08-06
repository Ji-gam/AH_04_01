from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snooze_reminders import SnoozeReminder


class SnoozeReminderRepository:
    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        medication_name: str,
        alarm_time: str,
        remind_at: datetime,
    ) -> SnoozeReminder:
        reminder = SnoozeReminder(
            profile_id=profile_id,
            source_type=source_type,
            source_id=source_id,
            medication_name=medication_name,
            alarm_time=alarm_time,
            remind_at=remind_at,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder

    async def list_due(self, session: AsyncSession, now: datetime) -> list[SnoozeReminder]:
        result = await session.execute(select(SnoozeReminder).where(SnoozeReminder.remind_at <= now))
        return list(result.scalars().all())

    async def delete(self, session: AsyncSession, reminder_id: int) -> bool:
        """[2026-08-06 버그 수정] missed_dose_escalation_repository.py의 같은 수정과 동일한
        이유 - uvicorn 워커 3개(Dockerfile --workers 3)가 각자 스케줄러를 돌리는데,
        "조회 → 처리 → 삭제" 순서라 여러 워커가 같은 예약을 동시에 읽어가 스누즈 재알림이
        중복 발송되는 문제가 있었다. 이 메서드를 "처리해도 되는지 먼저 확인하는 클레임"으로
        바꿔서(반환값 bool), 호출부(push_scheduler._send_due_snoozes)가 삭제를 먼저 시도하고
        성공한 워커만 실제 발송하도록 순서를 뒤집었다."""
        result = await session.execute(sa_delete(SnoozeReminder).where(SnoozeReminder.id == reminder_id))
        await session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]  # DML 결과엔 실제로 있음(스텁 누락)