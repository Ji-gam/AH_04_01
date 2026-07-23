import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.db.databases import AsyncSessionLocal
from app.models.medication_model import MedicationSchedule
from app.models.notification_schedules import DayOfWeek, FrequencyType, NotificationSchedule
from app.models.notification_settings import NotificationSetting
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.habit_repository import HabitRepository
from app.repositories.push_send_log_repository import PushSendLogRepository
from app.services.notification_settings_service import NotificationSettingsService
from app.services.periodic_report_service import PeriodicReportService
from app.services.push_service import PushService

# F-ADH-2(주간 피드백)/F-GOAL-3(월간 리포트)를 매분 틱마다 계산하지 않도록, 하루 중 이
# 시각의 틱에서만 요일/월말 여부를 확인한다(다른 복약 알림처럼 "정확히 이 분"에만 발송해야
# 하는 건 아니지만, 하루 한 번이면 충분해 굳이 매분 반복 조회할 필요가 없다).
_REPORT_SEND_HHMM = "09:00"

logger = logging.getLogger("app.push_scheduler")

# JS의 `Date.getDay()`(일요일=0 ~ 토요일=6)과 순서를 맞춰서, 프론트(dateUtils.ts의
# KOREAN_DAYS)와 "무슨 요일이 몇 번인지" 기준이 서로 어긋나지 않게 한다.
_JS_STYLE_KOREAN_DAYS = [
    DayOfWeek.SUN,
    DayOfWeek.MON,
    DayOfWeek.TUE,
    DayOfWeek.WED,
    DayOfWeek.THU,
    DayOfWeek.FRI,
    DayOfWeek.SAT,
]


def _is_due_today(schedule: NotificationSchedule, js_weekday: int) -> bool:
    """프론트 `isScheduleDueOnDate`(dateUtils.ts)와 동일한 판정 로직의 파이썬 버전."""
    if schedule.frequency_type == FrequencyType.DAILY:
        return True
    return schedule.target_day_of_week == _JS_STYLE_KOREAN_DAYS[js_weekday]


def _should_send(setting: NotificationSetting) -> bool:
    """복약 알림은 PRD(F-NTFY-6)가 "복약 필수 알림은 무음 시간대에도 발송"하도록 명시한
    필수 알림이라, push_enabled(사용자가 복약알림 자체를 꺼둔 경우)만 확인하고
    quiet_mode_enabled/무음 시간대는 일부러 확인하지 않는다 - 무음 시간대는 나중에
    라이프스타일 팁 등 비필수 알림(F-NTFY-6)에 실제 발송 로직이 생기면 그쪽에 적용해야
    한다."""
    return setting.push_enabled


class _SettingsCache:
    """스케줄 여러 개가 같은 프로필 소유일 수 있어(하루 2회/3회 복용 등), 한 틱 안에서는
    프로필당 한 번만 알림설정을 조회한다."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service = NotificationSettingsService()
        self._cache: dict[int, NotificationSetting] = {}

    async def get(self, profile_id: int) -> NotificationSetting:
        if profile_id not in self._cache:
            self._cache[profile_id] = await self._service.get_settings(self._session, profile_id)
        return self._cache[profile_id]


async def _send_due_notification_schedules(
    session: AsyncSession,
    push_service: PushService,
    settings: _SettingsCache,
    send_log_repo: PushSendLogRepository,
    now: datetime,
    js_weekday: int,
    current_hhmm: str,
) -> None:
    """복약알림(NotificationSchedule) - 화면의 "알림 추가"로 직접 만든 것."""
    result = await session.execute(select(NotificationSchedule).where(NotificationSchedule.is_active.is_(True)))
    for schedule in result.scalars().all():
        if schedule.alarm_time.strftime("%H:%M") != current_hhmm:
            continue
        if not _is_due_today(schedule, js_weekday):
            continue
        setting = await settings.get(schedule.profile_id)
        if not _should_send(setting):
            continue
        # 워커가 여러 개면 같은 1분 틱에 이 알림을 동시에 집으려 할 수 있다 - DB 유니크
        # 제약으로 선착순 클레임해서, 못 딴 워커는 조용히 건너뛴다(start_push_scheduler
        # docstring의 "알려진 한계" 참고).
        if not await send_log_repo.try_claim("notification_schedule", schedule.id, now.date(), current_hhmm):
            continue
        try:
            await push_service.send_to_profile_and_guardians(
                session,
                schedule.profile_id,
                title="복약 알림",
                body=f"{schedule.medication_name} 드실 시간이에요!",
                snooze_source=("notification_schedule", schedule.id),
                alarm_time=current_hhmm,
            )
        except Exception:
            logger.exception("알림 발송 중 오류 (notification_schedule_id=%s)", schedule.id)


async def _send_due_medication_schedules(
    session: AsyncSession,
    push_service: PushService,
    settings: _SettingsCache,
    send_log_repo: PushSendLogRepository,
    now: datetime,
    current_hhmm: str,
) -> None:
    """트랙커(MedicationSchedule) - 사진/검색으로 등록한 약. 화면(AlarmPage.tsx)의 "등록된
    알림" 목록엔 이것도 같이 병합해서 보여주고 있어서, 실제 발송도 똑같이 다뤄야 한다 - 이게
    빠져있어서 트랙커로 등록한 약은 시간이 와도 알림이 안 갔다(2026-07-18 확인된 버그, 여기서
    고침). 이 테이블엔 요일 개념이 없어서 times에 있는 시각과 매분 그냥 비교한다 - 매일
    반복이라고 보면 된다."""
    med_result = await session.execute(select(MedicationSchedule))
    med_schedules = list(med_result.scalars().all())
    # (T-MED-16) MedicationSchedule은 이제 item_seq만 들고 있어, 알림 문구에 쓸 약품명은
    # 마스터 데이터에서 일괄 조회해야 한다. AUTO_ 더미는 display_name으로 채워져 있다.
    drug_names = await DurDrugRepository().get_names_by_item_seqs(
        session, {s.item_seq for s in med_schedules if not s.display_name}
    )
    for med_schedule in med_schedules:
        # 이 테이블의 times는 등록 경로에 따라 "HH:MM"(신규 등록)과 "HH:MM:SS"(본인 화면
        # 수정 API가 초까지 붙여 저장하는 경우)가 섞여 있다 - 앞 5글자(HH:MM)만 잘라서
        # 비교해야 형식이 달라도 안전하게 매칭된다(2026-07-18, 이것 때문에 수정한 알림이
        # 하나도 안 울리던 버그를 여기서 고침).
        normalized_times = [t[:5] for t in med_schedule.times]
        if current_hhmm not in normalized_times:
            continue
        setting = await settings.get(med_schedule.profile_id)
        if not _should_send(setting):
            continue
        if not await send_log_repo.try_claim("medication_schedule", med_schedule.id, now.date(), current_hhmm):
            continue
        drug_name = med_schedule.display_name or drug_names.get(med_schedule.item_seq, med_schedule.item_seq)
        try:
            await push_service.send_to_profile_and_guardians(
                session,
                med_schedule.profile_id,
                title="복약 알림",
                body=f"{drug_name} 드실 시간이에요!",
                snooze_source=("medication_schedule", med_schedule.id),
                alarm_time=current_hhmm,
            )
        except Exception:
            logger.exception("알림 발송 중 오류 (medication_schedule_id=%s)", med_schedule.id)


async def _send_weekly_adherence_feedback_if_due(
    session: AsyncSession,
    settings: _SettingsCache,
    send_log_repo: PushSendLogRepository,
    report_service: PeriodicReportService,
    now: datetime,
    current_hhmm: str,
) -> None:
    """F-ADH-2 - 프로필마다 고른 요일(기본 토요일, NotificationSetting.adherence_feedback_day_of_week)
    09시에 지난 7일 복약 순응도 피드백을 보낸다. 복약 스케줄이 하나도 없는 프로필은 볼 것도
    없으니 건너뛴다."""
    if current_hhmm != _REPORT_SEND_HHMM:
        return
    today = now.date()
    result = await session.execute(select(MedicationSchedule.profile_id).distinct())
    week_start, week_end = today - timedelta(days=6), today
    for profile_id in result.scalars().all():
        setting = await settings.get(profile_id)
        if not _should_send(setting):
            continue
        if today.weekday() != setting.adherence_feedback_day_of_week:
            continue
        if not await send_log_repo.try_claim("adherence_weekly_feedback", profile_id, today, current_hhmm):
            continue
        try:
            await report_service.send_weekly_adherence_feedback(session, profile_id, week_start, week_end)
        except Exception:
            logger.exception("주간 순응도 피드백 발송 중 오류 (profile_id=%s)", profile_id)


async def _send_monthly_goal_report_if_due(
    session: AsyncSession,
    settings: _SettingsCache,
    send_log_repo: PushSendLogRepository,
    report_service: PeriodicReportService,
    now: datetime,
    current_hhmm: str,
) -> None:
    """F-GOAL-3 - 매월 마지막 날 09시에 그 달 복약 순응도 + 습관 달성률 리포트를 보낸다.
    실제 "목표"(F-GOAL-1) 기능이 아직 없어, 복약 스케줄이 있거나 이번 달 습관을 하나라도
    고른 프로필을 대상으로 한다(팀 결정: 두 지표 모두 리포트에 포함)."""
    if current_hhmm != _REPORT_SEND_HHMM:
        return
    today = now.date()
    if (today + timedelta(days=1)).day != 1:
        return
    month_start, month_end = today.replace(day=1), today

    med_result = await session.execute(select(MedicationSchedule.profile_id).distinct())
    habit_profile_ids = await HabitRepository().list_profile_ids_with_selections_in_range(
        session, month_start, month_end
    )
    profile_ids = set(med_result.scalars().all()) | set(habit_profile_ids)

    for profile_id in profile_ids:
        setting = await settings.get(profile_id)
        if not _should_send(setting):
            continue
        if not await send_log_repo.try_claim("goal_monthly_report", profile_id, today, current_hhmm):
            continue
        try:
            await report_service.send_monthly_goal_report(session, profile_id, month_start, month_end)
        except Exception:
            logger.exception("월간 달성 리포트 발송 중 오류 (profile_id=%s)", profile_id)


async def _check_and_send_due_notifications() -> None:
    now = datetime.now(tz=config.TIMEZONE)
    js_weekday = now.isoweekday() % 7  # Python isoweekday: 월=1~일=7 -> JS 기준(일=0~토=6)으로 변환
    current_hhmm = now.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        push_service = PushService()
        settings = _SettingsCache(session)
        send_log_repo = PushSendLogRepository()
        report_service = PeriodicReportService()
        await _send_due_notification_schedules(
            session, push_service, settings, send_log_repo, now, js_weekday, current_hhmm
        )
        await _send_due_medication_schedules(session, push_service, settings, send_log_repo, now, current_hhmm)
        await _send_weekly_adherence_feedback_if_due(
            session, settings, send_log_repo, report_service, now, current_hhmm
        )
        await _send_monthly_goal_report_if_due(session, settings, send_log_repo, report_service, now, current_hhmm)


async def _send_snoozed_notification(profile_id: int, source_type: str, source_id: int) -> None:
    """스누즈로 예약된 일회성 재발송(push_routers.py의 /push/snooze 참고). 예약 시점과
    실제 발송 시점 사이에 알림이 수정/삭제될 수 있어 문구를 다시 조회한다 - 꺼졌거나
    지워졌으면 조용히 건너뛴다. 무음 시간대는 일부러 확인하지 않는다 - 사용자가 명시적으로
    "이 시간에 다시 알려줘"를 선택한 거라, 그 사이 무음 시간대에 들어갔다고 억누르면 오히려
    스누즈의 의도(꼭 다시 알림받기)에 반한다. push_enabled(알림 자체를 꺼둔 경우)만 확인한다."""
    async with AsyncSessionLocal() as session:
        # 소유권 확인이 먼저다 - 알림설정 조회(get_or_create)가 없는 profile_id에 대해
        # notification_settings 행을 만들려다 FK 위반으로 죽는 걸 막는다(다른 프로필
        # 소유의 알림이거나, 그 사이 지워진 profile_id일 수 있음).
        title = "복약 알림"
        if source_type == "notification_schedule":
            schedule = await session.get(NotificationSchedule, source_id)
            if schedule is None or not schedule.is_active or schedule.profile_id != profile_id:
                return
            body = f"{schedule.medication_name} 드실 시간이에요! (미뤄둔 알림)"
        else:
            med_schedule = await session.get(MedicationSchedule, source_id)
            if med_schedule is None or med_schedule.profile_id != profile_id:
                return
            drug_name = med_schedule.display_name
            if not drug_name:
                names = await DurDrugRepository().get_names_by_item_seqs(session, {med_schedule.item_seq})
                drug_name = names.get(med_schedule.item_seq, med_schedule.item_seq)
            body = f"{drug_name} 드실 시간이에요! (미뤄둔 알림)"

        setting = await NotificationSettingsService().get_settings(session, profile_id)
        if not setting.push_enabled:
            return

        try:
            await PushService().send_to_profile_and_guardians(
                session, profile_id, title=title, body=body, snooze_source=(source_type, source_id)
            )
        except Exception:
            logger.exception(
                "스누즈 알림 발송 중 오류 (profile_id=%s, source_type=%s, source_id=%s)",
                profile_id,
                source_type,
                source_id,
            )


def schedule_snooze(
    scheduler: AsyncIOScheduler, profile_id: int, source_type: str, source_id: int, minutes: int
) -> None:
    """일회성 지연 작업을 등록한다. 반복 job(push_due_notifications)과 달리 이건 이 요청을
    받은 워커 프로세스 하나에서만 실행되니, ①번에서 다룬 "워커 여러 개면 중복 발송" 문제가
    여기엔 해당되지 않는다."""
    run_date = datetime.now(tz=config.TIMEZONE) + timedelta(minutes=minutes)
    scheduler.add_job(_send_snoozed_notification, "date", run_date=run_date, args=[profile_id, source_type, source_id])


def start_push_scheduler() -> AsyncIOScheduler:
    """[임시 구현] `docker-compose.yml`에 아직 celery-worker/celery-beat 서비스가 없고
    (그건 리더 소유 파일이라 별도 조율 필요 - `app/core/celery_app.py` 참고), 지금 웹푸시를
    급하게 살려야 해서 fastapi 프로세스 안에서 APScheduler로 1분마다 도는 방식으로 우선
    구현했다.

    [알려진 한계] uvicorn을 여러 워커/레플리카로 띄우면 이 스케줄러가 워커 개수만큼 동시에
    돈다 - 실제 발송(중복 알림)은 `PushSendLogRepository.try_claim`이 (알림 종류, id, 날짜,
    시각) 단위 DB 유니크 제약으로 선착순 클레임해서 워커 하나만 보내도록 막지만, 워커마다
    똑같이 DB를 조회하고 클레임을 시도하는 낭비 자체는 여전히 남아있다. 나중에 celery-beat이
    생기면 `_check_and_send_due_notifications`의 내용을 그대로 celery task로 옮기고 이
    스케줄러는 빼는 게 정석이다."""
    scheduler = AsyncIOScheduler(timezone=str(config.TIMEZONE))
    scheduler.add_job(_check_and_send_due_notifications, "interval", minutes=1, id="push_due_notifications")
    scheduler.start()
    logger.info("푸시 스케줄러 시작됨 (1분 간격, 임시 인프로세스 방식)")
    return scheduler
