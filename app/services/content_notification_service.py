import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.repositories.disease_entry_repository import DiagnosisEntryRepository
from app.services.disease_code_mapper import disease_code_to_enum
from app.services.notification_settings_service import NotificationSettingsService
from app.services.push_service import PushService
from app.services.quiet_hours import is_in_quiet_hours

logger = logging.getLogger("app.content_notification_service")


class ContentNotificationService:
    """새 건강 콘텐츠(라이프스타일 팁 등)가 생성되면, 그 질환을 진단병력에 등록해둔
    프로필 중 lifestyle_tip_enabled를 켜둔 사람에게 알린다(F-NTFY-6).

    오프라인 배치 생성(app/scripts/generate_health_content.py)은 여러 질환×카테고리를
    한 번에 대량 생성하는 사전 캐시 워밍 작업이라, 여기 연결하면 알림이 한꺼번에 쏟아진다 -
    그래서 관리자가 명시적으로 하나씩 트리거하는 온라인 단건 생성
    (ContentGenerationService.generate_and_save, "더보기 > 관리자 컨텐츠생성")에만
    연결한다 - 공지/마케팅과 같은 "명시적 생성 → 알림" 패턴."""

    def __init__(self) -> None:
        self._diagnosis_repo = DiagnosisEntryRepository()
        self._settings_service = NotificationSettingsService()
        self._push_service = PushService()

    async def notify_new_content(self, session: AsyncSession, disease_code: str, title: str) -> None:
        try:
            disease = disease_code_to_enum(disease_code)
            if disease is None:
                return
            profile_ids = await self._diagnosis_repo.list_profile_ids_by_disease(session, disease)
            now = datetime.now(tz=config.TIMEZONE)
            for profile_id in profile_ids:
                try:
                    setting = await self._settings_service.get_settings(session, profile_id)
                    if not setting.lifestyle_tip_enabled or is_in_quiet_hours(setting, now):
                        continue
                    await self._push_service.send_to_profile(session, profile_id, title="🌿 새 건강 콘텐츠", body=title)
                except Exception:
                    logger.exception("콘텐츠 알림 발송 실패 (profile_id=%s)", profile_id)
        except Exception:
            logger.exception("콘텐츠 알림 브로드캐스트 실패")
