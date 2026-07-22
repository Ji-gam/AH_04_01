from datetime import datetime

from app.models.notification_settings import NotificationSetting


def is_in_quiet_hours(setting: NotificationSetting, now: datetime) -> bool:
    """무음 모드가 꺼져있으면 항상 False. 자정을 넘어가는 시간대(예: 22:00~07:00)도 처리한다.

    복약 필수 알림(push_scheduler.py)은 이 체크를 아예 거치지 않는다 - PRD(F-NTFY-6)가
    "복약 필수 알림은 무음 시간대에도 발송"하도록 명시적으로 예외를 뒀기 때문이다. 챗봇
    답변/공지/마케팅/라이프스타일 콘텐츠 등 비필수 알림에서만 이 함수를 쓴다."""
    if not setting.quiet_mode_enabled:
        return False
    now_time = now.time()
    quiet_start, quiet_end = setting.quiet_start, setting.quiet_end
    if quiet_start <= quiet_end:
        return quiet_start <= now_time < quiet_end
    return now_time >= quiet_start or now_time < quiet_end
