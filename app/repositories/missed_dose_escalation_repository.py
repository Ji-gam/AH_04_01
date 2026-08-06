from datetime import date, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.missed_dose_escalations import MissedDoseEscalation


class MissedDoseEscalationRepository:
    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        medication_name: str,
        alarm_time: str,
        intake_date: date,
        check_at: datetime,
    ) -> MissedDoseEscalation:
        escalation = MissedDoseEscalation(
            profile_id=profile_id,
            source_type=source_type,
            source_id=source_id,
            medication_name=medication_name,
            alarm_time=alarm_time,
            intake_date=intake_date,
            check_at=check_at,
        )
        session.add(escalation)
        await session.commit()
        await session.refresh(escalation)
        return escalation

    async def list_due(self, session: AsyncSession, now: datetime) -> list[MissedDoseEscalation]:
        result = await session.execute(select(MissedDoseEscalation).where(MissedDoseEscalation.check_at <= now))
        return list(result.scalars().all())

    async def delete(self, session: AsyncSession, escalation_id: int) -> bool:
        """[2026-08-06 버그 수정] uvicorn이 워커 3개로 뜨는데(Dockerfile --workers 3),
        각 워커가 자기 프로세스 안에서 매분 스케줄러를 따로 돌린다. 원래는
        `list_due`로 조회 → 처리 → 이 메서드로 삭제 순서였는데, 그 사이 시간차에
        여러 워커가 같은 예약 행을 동시에 읽어가서 똑같은 미확인 알림을 최대
        3번(워커 수만큼) 중복 발송하는 문제가 있었다("알람이 여러 개 주르륵 온다").

        DELETE 자체는 행 단위로 원자적이라, 여러 워커가 같은 id를 동시에 지우려
        해도 실제로 삭제에 성공하는(rowcount>0) 건 딱 하나뿐이다. 그래서 호출
        순서를 뒤집어 이 메서드를 "처리해도 되는지 먼저 확인하는 클레임"으로 쓴다
        - `_send_due_items`가 `PushSendLogRepository.try_claim()`으로 하는 것과
        같은 패턴이다. 반환값이 False면 다른 워커가 이미 처리했다는 뜻이니 그
        예약은 조용히 건너뛰면 된다."""
        result = await session.execute(sa_delete(MissedDoseEscalation).where(MissedDoseEscalation.id == escalation_id))
        await session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined]  # DML 결과엔 실제로 있음(스텁 누락)
