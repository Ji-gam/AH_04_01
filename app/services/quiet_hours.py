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


def is_in_lifestyle_tip_window(setting: NotificationSetting, now: datetime) -> bool:
    """F-NTFY-6 - 라이프스타일 팁 전용 시간대. is_in_quiet_hours와 별개의 추가 제약이다
    (둘 다 통과해야 발송됨) - 꺼져있으면(기본값) 항상 True라 기존 동작과 같다. 자정을
    넘어가는 시간대도 is_in_quiet_hours와 동일하게 처리한다."""
    if not setting.lifestyle_tip_window_enabled:
        return True
    now_time = now.time()
    start, end = setting.lifestyle_tip_start, setting.lifestyle_tip_end
    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def is_lifestyle_tip_interval_ok(setting: NotificationSetting, now: datetime) -> bool:
    """F-NTFY-6 - 마지막으로 팁을 받은 지 lifestyle_tip_min_interval_days일이 지났는지.
    0이면(기본값) 제한 없음. 발송 성공 시 호출자가 setting.lifestyle_tip_last_sent_at을
    now로 갱신해야 다음 판정에 반영된다(이 함수 자체는 갱신하지 않음, 순수 판정만)."""
    if setting.lifestyle_tip_min_interval_days <= 0:
        return True
    if setting.lifestyle_tip_last_sent_at is None:
        return True
    return (now - setting.lifestyle_tip_last_sent_at).days >= setting.lifestyle_tip_min_interval_days
