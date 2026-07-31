from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.chat import ChatMessage, ChatSession
from app.models.family_link import FamilyLink, FamilyLinkStatus
from app.models.medication_intake import MedicationIntakeLog
from app.models.medication_model import MedicationSchedule
from app.models.notification_log import NotificationLog
from app.models.users import User
from app.repositories.dur_drug_repository import DurDrugRepository


class OpsStatsRepository:
    """(2026-07-28) 관리자 대시보드 "운영 현황" 탭 전용 집계 쿼리 모음. 전부 익명 집계라
    개인 식별 정보는 안 다룬다 - 다만 "자주 등록되는 약품"은 인원이 아주 적은 항목까지
    노출되면 재식별 위험이 있어 min_count 미만은 결과에서 아예 뺀다."""

    async def active_user_count(self, session: AsyncSession, since: datetime) -> int:
        """DAU/WAU - User.last_login 기준(로그인 자체가 있어야 "활성"으로 친다)."""
        stmt = select(func.count()).select_from(User).where(User.last_login >= since)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def top_drugs(self, session: AsyncSession, min_count: int = 3, limit: int = 10) -> list[tuple[str, int]]:
        """등록 건수 기준 상위 약품. min_count 미만인 항목(등록자가 아주 적은 약)은
        결과에서 아예 빼서, 희귀 약 하나로 특정 소수 사용자가 역추적되는 걸 막는다."""
        stmt = (
            select(MedicationSchedule.item_seq, func.count().label("cnt"))
            .group_by(MedicationSchedule.item_seq)
            .having(func.count() >= min_count)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()
        if not rows:
            return []
        item_seqs = {r.item_seq for r in rows}
        names = await DurDrugRepository().get_names_by_item_seqs(session, item_seqs)
        return [(names.get(r.item_seq, r.item_seq), r.cnt) for r in rows]

    async def news_count_by_source(self, session: AsyncSession) -> dict[str, int]:
        """(T-LLM-6) 매체별 수집된 건강 뉴스 수. 소스를 늘려갈 때(7단계) 어느 매체가 실제로
        기사를 주는지 보려고 둔다 - 조회수 추적이 없어서 인기순은 여전히 못 보여준다.
        표시명(source_name)으로 묶는 이유: 관리자 화면에 그대로 보여줄 값이기 때문."""
        from app.models.health_news import HealthNews

        stmt = select(HealthNews.source_name, func.count()).group_by(HealthNews.source_name)
        result = await session.execute(stmt)
        return {str(row[0]): row[1] for row in result.all()}

    async def chat_usage_trend(self, session: AsyncSession, days: int = 7) -> list[tuple[str, int]]:
        since = datetime.now(tz=config.TIMEZONE) - timedelta(days=days - 1)
        day_col = func.date(ChatMessage.created_at)
        stmt = (
            select(day_col.label("day"), func.count().label("cnt"))
            .where(ChatMessage.created_at >= since)
            .group_by(day_col)
        )
        result = await session.execute(stmt)
        counts_by_day = {str(row.day): row.cnt for row in result.all()}
        trend: list[tuple[str, int]] = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            trend.append((str(day), counts_by_day.get(str(day), 0)))
        return trend

    async def active_chat_session_count(self, session: AsyncSession, since: datetime) -> int:
        stmt = select(func.count()).select_from(ChatSession).where(ChatSession.updated_at >= since)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def notification_count_trend(self, session: AsyncSession, days: int = 7) -> list[tuple[str, int]]:
        """(주의) 실제 브라우저 전달 성공/실패 여부는 기록하지 않아 성공률은 못 보여주고,
        "발송을 시도(결정)한 건수"만 보여준다."""
        since = datetime.now(tz=config.TIMEZONE) - timedelta(days=days - 1)
        day_col = func.date(NotificationLog.created_at)
        stmt = (
            select(day_col.label("day"), func.count().label("cnt"))
            .where(NotificationLog.created_at >= since)
            .group_by(day_col)
        )
        result = await session.execute(stmt)
        counts_by_day = {str(row.day): row.cnt for row in result.all()}
        trend: list[tuple[str, int]] = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            trend.append((str(day), counts_by_day.get(str(day), 0)))
        return trend

    async def family_link_count(self, session: AsyncSession) -> int:
        stmt = select(func.count()).select_from(FamilyLink).where(FamilyLink.status == FamilyLinkStatus.ACCEPTED)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def adherence_rate(self, session: AsyncSession, days: int = 7) -> float | None:
        """(근사치) 등록약의 하루 복용 횟수(JSON_LENGTH(times)) × 기간을 "기대 체크 수"로,
        실제 medication_intake_logs 건수를 "실제 체크 수"로 나눈 근사 순응도다. 스케줄이
        기간 중간에 등록/삭제된 경우까지 정확히 반영하진 않는 단순 근사치 - 운영 참고용."""
        expected_per_day_stmt = select(func.sum(func.json_length(MedicationSchedule.times)))
        expected_result = await session.execute(expected_per_day_stmt)
        expected_per_day = expected_result.scalar_one() or 0
        if expected_per_day == 0:
            return None

        since_date = date.today() - timedelta(days=days - 1)
        checked_stmt = (
            select(func.count()).select_from(MedicationIntakeLog).where(MedicationIntakeLog.intake_date >= since_date)
        )
        checked_result = await session.execute(checked_stmt)
        checked = checked_result.scalar_one()

        expected_total = expected_per_day * days
        if expected_total == 0:
            return None
        return min(1.0, checked / expected_total)

    async def withdrawal_trend(self, session: AsyncSession, days: int = 30) -> list[tuple[str, int]]:
        """(근사치) 탈퇴 1건당 진단병력/가족력 개수만큼 여러 행이 남을 수 있어 정확한
        "탈퇴 인원 수"는 아니고 "탈퇴 관련 통계 레코드가 남은 날짜 분포" 정도로 참고만."""
        from app.models.withdrawn_stats import WithdrawnHealthStat

        since = datetime.now(tz=config.TIMEZONE) - timedelta(days=days - 1)
        day_col = func.date(WithdrawnHealthStat.created_at)
        stmt = (
            select(day_col.label("day"), func.count(func.distinct(day_col)).label("cnt"))
            .where(WithdrawnHealthStat.created_at >= since)
            .group_by(day_col)
        )
        result = await session.execute(stmt)
        counts_by_day = {str(row.day): row.cnt for row in result.all()}
        trend: list[tuple[str, int]] = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            trend.append((str(day), counts_by_day.get(str(day), 0)))
        return trend

    async def ai_worker_status(self) -> str:
        """AI-worker 컨테이너가 살아있는지 가벼운 GET으로 확인. 전용 헬스체크 엔드포인트가
        따로 없어서 루트 경로에 짧은 타임아웃으로 붙어보고, 응답이 오면(설령 404여도)
        "살아있다"로 판단한다 - 완전히 연결이 안 되거나 타임아웃나면 "다운"으로 본다."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get(config.AI_WORKER_BASE_URL)
            return "ok"
        except Exception:
            return "down"
