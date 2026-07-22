import logging
from datetime import datetime, time, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.core.db.databases import AsyncSessionLocal
from app.models.medication_model import MedicationSchedule
from app.models.notification_schedules import DayOfWeek, FrequencyType, NotificationSchedule
from app.models.notification_settings import NotificationSetting
from app.repositories.dur_drug_repository import DurDrugRepository
from app.services.notification_settings_service import NotificationSettingsService
from app.services.push_service import PushService

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


def _is_in_quiet_hours(now_time: time, quiet_start: time, quiet_end: time) -> bool:
    if quiet_start <= quiet_end:
        return quiet_start <= now_time < quiet_end
    # 자정을 넘어가는 무음 시간대(예: 22:00~07:00) - 시작 이후 또는 종료 이전이면 무음이다.
    return now_time >= quiet_start or now_time < quiet_end


def _should_send(setting: NotificationSetting, now: datetime) -> bool:
    """알림설정(NotificationSettingsPage.tsx가 저장한 값)을 확인해, 사용자가 복약알림
    푸시를 꺼뒀거나 지금이 무음 시간대면 보내지 않는다."""
    if not setting.push_enabled:
        return False
    if setting.quiet_mode_enabled and _is_in_quiet_hours(now.time(), setting.quiet_start, setting.quiet_end):
        return False
    return True


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
        if not _should_send(setting, now):
            continue
        try:
            await push_service.send_to_profile_and_guardians(
                session,
                schedule.profile_id,
                title="복약 알림",
                body=f"{schedule.medication_name} 드실 시간이에요!",
                snooze_source=("notification_schedule", schedule.id),
            )
        except Exception:
            logger.exception("알림 발송 중 오류 (notification_schedule_id=%s)", schedule.id)


async def _send_due_medication_schedules(
    session: AsyncSession,
    push_service: PushService,
    settings: _SettingsCache,
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
        if not _should_send(setting, now):
            continue
        drug_name = med_schedule.display_name or drug_names.get(med_schedule.item_seq, med_schedule.item_seq)
        try:
            await push_service.send_to_profile_and_guardians(
                session,
                med_schedule.profile_id,
                title="복약 알림",
                body=f"{drug_name} 드실 시간이에요!",
                snooze_source=("medication_schedule", med_schedule.id),
            )
        except Exception:
            logger.exception("알림 발송 중 오류 (medication_schedule_id=%s)", med_schedule.id)


async def _check_and_send_due_notifications() -> None:
    now = datetime.now(tz=config.TIMEZONE)
    js_weekday = now.isoweekday() % 7  # Python isoweekday: 월=1~일=7 -> JS 기준(일=0~토=6)으로 변환
    current_hhmm = now.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        push_service = PushService()
        settings = _SettingsCache(session)
        await _send_due_notification_schedules(session, push_service, settings, now, js_weekday, current_hhmm)
        await _send_due_medication_schedules(session, push_service, settings, now, current_hhmm)


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
    돌아서 같은 알림이 중복 발송될 수 있다 - 지금은 로컬/개발 환경(워커 1개)에서만 쓰는 걸
    전제로 한다. 나중에 celery-beat이 생기면 `_check_and_send_due_notifications`의 내용을
    그대로 celery task로 옮기고 이 스케줄러는 빼는 게 정석이다."""
    scheduler = AsyncIOScheduler(timezone=str(config.TIMEZONE))
    scheduler.add_job(_check_and_send_due_notifications, "interval", minutes=1, id="push_due_notifications")
    scheduler.start()
    logger.info("푸시 스케줄러 시작됨 (1분 간격, 임시 인프로세스 방식)")
    return scheduler
