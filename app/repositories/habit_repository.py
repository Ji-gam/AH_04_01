from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.databases import AsyncSessionLocal
from app.models.habit_logs import HabitLog
from app.models.habit_selections import HabitSelection
from app.models.habit_subtype_suggestions import HabitSubtypeSuggestion


class HabitRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        # save_subtype_suggestions()가 호출자의 session과 별개로 독립된 세션을 열 때 쓴다
        # (그 이유는 아래 docstring 참고). 테스트에서는 실제 앱과 같은 DB(ai_health)가 아니라
        # 격리된 test DB를 쓰도록 TestSessionLocal로 오버라이드한다.
        self._session_factory = session_factory or AsyncSessionLocal

    async def list_subtype_suggestions(
        self, session: AsyncSession, disease_subtype_id: int
    ) -> list[HabitSubtypeSuggestion]:
        result = await session.execute(
            select(HabitSubtypeSuggestion)
            .where(HabitSubtypeSuggestion.disease_subtype_id == disease_subtype_id)
            .order_by(HabitSubtypeSuggestion.slot)
        )
        return list(result.scalars().all())

    async def save_subtype_suggestions(
        self,
        disease_subtype_id: int,
        suggestions: list[dict],
    ) -> list[HabitSubtypeSuggestion]:
        """한 진단명에 대해 생성된 습관 여러 개(slot 0부터)를 한 번에 저장한다.

        캐시 미스 판단(list_subtype_suggestions)과 이 저장 사이엔 잠금이 없어, 같은 진단명에
        대한 두 요청이 동시에 캐시가 비어있는 걸 보고 둘 다 LLM 호출 + 저장을 시도할 수 있다
        (실제로 프론트가 GET /habits/recommendations와 GET /habits/today를 Promise.all로
        동시에 호출해 재현됨 - PR #168 리뷰). 늦게 커밋을 시도하는 쪽은 (disease_subtype_id,
        slot) unique 제약 위반으로 실패하는데, 이건 진짜 오류가 아니라 "다른 요청이 먼저
        저장했다"는 신호이므로 그 결과를 그대로 재조회해서 반환해야 한다.

        [주의] 호출자의 session을 받지 않고 독립된 새 세션을 직접 연다 - 이유가 두 가지다.
        1) 실패 시 롤백이 필요한데, 호출자의 session으로 롤백하면 그 세션이 이미 로드해둔 다른
           객체(예: profile.diagnosis_entries)까지 전부 만료(expire)되고, 그 뒤 그 객체를
           다시 쓰면 비동기 컨텍스트 밖에서 지연로딩이 시도되어 MissingGreenlet 에러로
           이어진다(세이브포인트로도 안 됨 - 2번 참고). 독립된 세션이면 그 세션 안의 객체만
           영향받고 호출자 세션은 전혀 건드리지 않는다.
        2) MySQL 기본 격리수준(REPEATABLE READ)에서는, 충돌 후 "같은" 트랜잭션으로 재조회해도
           트랜잭션 시작 시점 스냅샷 때문에 다른 트랜잭션이 막 커밋한 행이 안 보일 수 있다
           (세이브포인트만 롤백하고 재조회해도 이 문제가 남음 - 실제로 재현되어 알게 됨). 새
           세션은 새 트랜잭션이라 이 문제가 없다."""
        rows = [
            HabitSubtypeSuggestion(disease_subtype_id=disease_subtype_id, slot=slot, **suggestion)
            for slot, suggestion in enumerate(suggestions)
        ]
        async with self._session_factory() as write_session:
            write_session.add_all(rows)
            try:
                await write_session.commit()
            except IntegrityError:
                await write_session.rollback()
                existing = await self.list_subtype_suggestions(write_session, disease_subtype_id)
                if existing:
                    return existing
                raise
            for row in rows:
                await write_session.refresh(row)
            return rows

    async def list_selected_keys(self, session: AsyncSession, profile_id: int, select_date: date) -> list[str]:
        result = await session.execute(
            select(HabitSelection.habit_key).where(
                HabitSelection.profile_id == profile_id, HabitSelection.select_date == select_date
            )
        )
        return list(result.scalars().all())

    async def replace_selection(
        self, session: AsyncSession, profile_id: int, select_date: date, habit_keys: list[str]
    ) -> None:
        """오늘 선택을 통째로 교체한다(다시 고르면 이전 선택은 사라짐) - 몇 개를 고르든(0개 포함)
        그대로 반영되는 게 의도라, 증분 추가/삭제가 아니라 전체 삭제 후 재삽입이 제일 단순하다."""
        await session.execute(
            delete(HabitSelection).where(
                HabitSelection.profile_id == profile_id, HabitSelection.select_date == select_date
            )
        )
        for key in habit_keys:
            session.add(HabitSelection(profile_id=profile_id, select_date=select_date, habit_key=key))
        await session.commit()

    async def list_logs_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> list[HabitLog]:
        result = await session.execute(
            select(HabitLog).where(HabitLog.profile_id == profile_id, HabitLog.log_date == log_date)
        )
        return list(result.scalars().all())

    async def list_selections_for_range(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> list[HabitSelection]:
        """F-GOAL-3 월간 리포트용 - 이 기간에 하루라도 선택된 (날짜, habit_key) 전체."""
        result = await session.execute(
            select(HabitSelection).where(
                HabitSelection.profile_id == profile_id,
                HabitSelection.select_date >= start_date,
                HabitSelection.select_date <= end_date,
            )
        )
        return list(result.scalars().all())

    async def list_logs_for_range(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> list[HabitLog]:
        """F-GOAL-3 월간 리포트용 - 이 기간의 진행량 전체."""
        result = await session.execute(
            select(HabitLog).where(
                HabitLog.profile_id == profile_id,
                HabitLog.log_date >= start_date,
                HabitLog.log_date <= end_date,
            )
        )
        return list(result.scalars().all())

    async def list_profile_ids_with_selections_in_range(
        self, session: AsyncSession, start_date: date, end_date: date
    ) -> list[int]:
        """F-GOAL-3 스케줄러용 - 이 기간에 습관을 하나라도 고른 프로필 id 목록."""
        result = await session.execute(
            select(HabitSelection.profile_id)
            .where(HabitSelection.select_date >= start_date, HabitSelection.select_date <= end_date)
            .distinct()
        )
        return list(result.scalars().all())

    async def get_log(self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str) -> HabitLog | None:
        result = await session.execute(
            select(HabitLog).where(
                HabitLog.profile_id == profile_id,
                HabitLog.log_date == log_date,
                HabitLog.habit_key == habit_key,
            )
        )
        return result.scalar_one_or_none()

    async def increment_progress(
        self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str, cap: int
    ) -> HabitLog:
        log = await self.get_log(session, profile_id, log_date, habit_key)
        if log is None:
            log = HabitLog(profile_id=profile_id, log_date=log_date, habit_key=habit_key, progress=0)
            session.add(log)
        log.progress = min(log.progress + 1, cap)
        await session.commit()
        await session.refresh(log)
        return log
