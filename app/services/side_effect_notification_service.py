import logging
from datetime import datetime
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.repositories.dur_drug_repository import DurDrugRepository
from app.services.notification_settings_service import NotificationSettingsService
from app.services.push_service import PushService
from app.services.quiet_hours import is_in_quiet_hours

logger = logging.getLogger("app.side_effect_notification_service")

_SIDE_EFFECT_SUMMARY_LIMIT = 60


def _build_consult_url(drug_name: str) -> str:
    """알림의 "불편한 증상이 있어요" 액션 버튼이 열 딥링크. 탭이 완전히 닫혀있어도
    service-worker의 clients.openWindow(url)로 열리므로 React Router의 location.state를
    못 쓴다 - 대신 쿼리 파라미터로 자동 질문 문구를 실어보내고, ChatPage.tsx가 마운트
    시점에 이걸 읽어 자동 전송한다(기존 location.state 방식과 나란히 지원)."""
    message = f"{drug_name} 복용 중인데 부작용이 걱정돼요. 어떤 증상을 조심해야 하나요?"
    return f"/chat?autoMessage={quote(message)}"


class SideEffectNotificationService:
    """약 등록 즉시(F-NTFY-5) e약은요 부작용(side_effects) 문구가 있으면 안내 푸시를 보낸다.

    실제 복용 시각까지 기다리지 않고 등록 시점에 바로 보낸다 - "언제 처음 먹는지" 추적할
    새 상태가 필요 없어 기존 스케줄 생성 흐름에 바로 얹을 수 있다(사용자가 선택한 저복잡도
    설계). 복약 필수 알림(push_scheduler.py)과 달리 이건 1회성 참고 안내라 quiet_hours의
    "비필수" 취급을 그대로 따른다(챗봇 답변/공지/라이프스타일 콘텐츠와 동일한 취급)."""

    def __init__(
        self,
        dur_drug_repository: DurDrugRepository | None = None,
        notification_settings_service: NotificationSettingsService | None = None,
        push_service: PushService | None = None,
    ) -> None:
        self._dur_drug_repository = dur_drug_repository or DurDrugRepository()
        self._notification_settings_service = notification_settings_service or NotificationSettingsService()
        self._push_service = push_service or PushService()

    async def notify_if_side_effects(self, session: AsyncSession, profile_id: int, drug_name: str) -> None:
        try:
            result = await self._dur_drug_repository.drug_data(session, drug_name)
            side_effects = next((p.side_effects for p in result.profiles if p.side_effects), None)
            if not side_effects:
                return

            setting = await self._notification_settings_service.get_settings(session, profile_id)
            now = datetime.now(tz=config.TIMEZONE)
            if not setting.push_enabled or is_in_quiet_hours(setting, now):
                return

            summary = (
                side_effects
                if len(side_effects) <= _SIDE_EFFECT_SUMMARY_LIMIT
                else side_effects[:_SIDE_EFFECT_SUMMARY_LIMIT] + "…"
            )
            await self._push_service.send_to_profile(
                session,
                profile_id,
                title=f"⚠️ {drug_name} 복용 전 확인하세요",
                body=f"부작용: {summary}",
                consult_url=_build_consult_url(drug_name),
            )
        except Exception:
            logger.exception("부작용 사전 안내 알림 발송 실패 (profile_id=%s, drug_name=%s)", profile_id, drug_name)
