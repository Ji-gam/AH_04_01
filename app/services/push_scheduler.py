import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core import config
from app.core.db.databases import AsyncSessionLocal
from app.models.medication_model import MedicationSchedule
from app.models.notification_schedules import DayOfWeek, FrequencyType, NotificationSchedule
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.push_send_log_repository import PushSendLogRepository
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


async def _check_and_send_due_notifications() -> None:
    now = datetime.now(tz=config.TIMEZONE)
    js_weekday = now.isoweekday() % 7  # Python isoweekday: 월=1~일=7 -> JS 기준(일=0~토=6)으로 변환
    current_hhmm = now.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        push_service = PushService()
        send_log_repo = PushSendLogRepository()
        today = now.date()

        # 1) 복약알림(NotificationSchedule) - 화면의 "알림 추가"로 직접 만든 것.
        result = await session.execute(select(NotificationSchedule).where(NotificationSchedule.is_active.is_(True)))
        for schedule in result.scalars().all():
            if schedule.alarm_time.strftime("%H:%M") != current_hhmm:
                continue
            if not _is_due_today(schedule, js_weekday):
                continue
            # 워커가 여러 개면 같은 1분 틱에 이 알림을 동시에 집으려 할 수 있다 - DB 유니크
            # 제약으로 선착순 클레임해서, 못 딴 워커는 조용히 건너뛴다(start_push_scheduler
            # docstring의 "알려진 한계" 참고).
            if not await send_log_repo.try_claim("notification_schedule", schedule.id, today, current_hhmm):
                continue
            try:
                await push_service.send_to_profile_and_guardians(
                    session,
                    schedule.profile_id,
                    title="복약 알림",
                    body=f"{schedule.medication_name} 드실 시간이에요!",
                )
            except Exception:
                logger.exception("알림 발송 중 오류 (notification_schedule_id=%s)", schedule.id)

        # 2) 트랙커(MedicationSchedule) - 사진/검색으로 등록한 약. 화면(AlarmPage.tsx)의
        # "등록된 알림" 목록엔 이것도 같이 병합해서 보여주고 있어서, 실제 발송도 똑같이
        # 다뤄야 한다 - 이게 빠져있어서 트랙커로 등록한 약은 시간이 와도 알림이 안 갔다
        # (2026-07-18 확인된 버그, 여기서 고침). 이 테이블엔 요일/on-off 개념이 없어서
        # (프론트의 "끄기"도 로컬 전용 음소거일 뿐 서버엔 없음) times에 있는 시각과
        # 매분 그냥 비교한다 - 매일 반복이라고 보면 된다.
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
            if not await send_log_repo.try_claim("medication_schedule", med_schedule.id, today, current_hhmm):
                continue
            drug_name = med_schedule.display_name or drug_names.get(med_schedule.item_seq, med_schedule.item_seq)
            try:
                await push_service.send_to_profile_and_guardians(
                    session,
                    med_schedule.profile_id,
                    title="복약 알림",
                    body=f"{drug_name} 드실 시간이에요!",
                )
            except Exception:
                logger.exception("알림 발송 중 오류 (medication_schedule_id=%s)", med_schedule.id)


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
