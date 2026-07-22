import json
import logging

from fastapi import HTTPException, status
from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.family_link import FamilyLinkStatus
from app.repositories.family_repository import FamilyRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.push_subscription_repository import PushSubscriptionRepository

logger = logging.getLogger("app.push_service")


class PushService:
    def __init__(self) -> None:
        self._repo = PushSubscriptionRepository()
        self._family_repo = FamilyRepository()
        self._profile_repo = ProfileRepository()

    def get_vapid_public_key(self) -> str:
        """프론트가 `pushManager.subscribe()`에 넘길 공개키. 서버에서만 비밀키를 쥐고 있고,
        공개키만 프론트에 내려준다(웹푸시 표준 - 이 공개키로 암호화된 메시지는 이 서버의
        비밀키로만 복호화/서명 검증이 가능하다)."""
        if not config.VAPID_PUBLIC_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="웹푸시가 아직 설정되지 않았습니다 (VAPID 키 미설정).",
            )
        return config.VAPID_PUBLIC_KEY

    async def subscribe(
        self, session: AsyncSession, profile_id: int, endpoint: str, p256dh_key: str, auth_key: str
    ) -> None:
        """같은 endpoint로 이미 구독돼 있으면(같은 브라우저에서 재구독) 보통은 그냥
        무시한다 - 브라우저가 새로고침마다 구독을 다시 요청하는 경우가 흔해서, 매번 새
        row가 쌓이지 않게 하기 위함. 다만 그 endpoint의 주인(profile_id)이 지금 요청한
        사람과 다르면(같은 브라우저에서 계정을 바꿔 로그인한 뒤 다시 "알림 켜기"를 누른
        경우) 그 브라우저는 이제 이 사람 것이니 profile_id를 갱신한다 - 안 그러면 나중에
        로그인한 사람은 영영 구독이 안 되는 조용한 버그가 생긴다(2026-07-18 확인)."""
        existing = await self._repo.get_by_endpoint(session, endpoint)
        if existing:
            if existing.profile_id != profile_id:
                await self._repo.update_profile_id(session, existing.id, profile_id)
            return
        await self._repo.create(session, profile_id, endpoint, p256dh_key, auth_key)

    async def unsubscribe(self, session: AsyncSession, endpoint: str) -> None:
        await self._repo.delete_by_endpoint(session, endpoint)

    async def send_to_profile(
        self,
        session: AsyncSession,
        profile_id: int,
        title: str,
        body: str,
        snooze_source: tuple[str, int] | None = None,
        alarm_time: str | None = None,
        consult_url: str | None = None,
    ) -> None:
        """이 프로필이 구독해둔 모든 기기(WEB만 - IOS/ANDROID는 나중에 네이티브 패키징 시
        별도 발송 경로 예정)에 푸시를 보낸다. 구독 하나가 실패해도(예: 브라우저에서
        구독 취소했는데 서버 DB에는 아직 남아있는 경우) 나머지 기기 발송은 계속한다.

        snooze_source=(source_type, source_id)를 주면 알림에 "30분 후 다시"/"빈도 줄이기"
        액션 버튼을 붙인다(service-worker.js가 payload.actions/data를 그대로 showNotification에
        넘긴다) - 복약알림 본인 몫에만 쓰고, 가족에게 전달하는 사본에는 안 붙인다(스누즈/빈도
        조정은 본인이 결정할 일이라 가족이 대신 할 수 있으면 안 된다). 액션 버튼은 브라우저마다
        보통 최대 2개까지만 확실히 렌더링돼서(F-NTFY-3), "1시간 후 다시"는 "빈도 줄이기"로
        교체했다 - 둘 다 넣으면 일부 기기에서 3번째 버튼이 아예 안 보일 수 있어서다.

        alarm_time("HH:MM")은 medication_schedule 빈도 줄이기 전용 - 그 스케줄의 여러 시각
        중 "이 알림이 울린 시각"만 정확히 골라 뺄 수 있도록 함께 실어보낸다. 모르면(예: 스누즈
        후 재발송) 생략해도 된다 - 서버가 alarm_time 없이는 조용히 아무것도 지우지 않는다.

        consult_url을 주면(F-NTFY-5 부작용 사전 안내 전용) "불편한 증상이 있어요" 액션
        버튼을 붙인다 - service-worker.js가 클릭 시 이 URL(챗봇 자동 질문 딥링크)을 연다.
        snooze_source와 동시에 쓰는 경우는 없다(용도가 겹치지 않음)."""
        if not config.VAPID_PRIVATE_KEY:
            logger.warning("VAPID 비밀키가 설정되지 않아 푸시 발송을 건너뜁니다.")
            return

        payload: dict = {"title": title, "body": body}
        if snooze_source is not None:
            source_type, source_id = snooze_source
            data: dict = {"profile_id": profile_id, "source_type": source_type, "source_id": source_id}
            if alarm_time is not None:
                data["alarm_time"] = alarm_time
            payload["data"] = data
            payload["actions"] = [
                {"action": "snooze_30", "title": "30분 후 다시"},
                {"action": "reduce_freq", "title": "빈도 줄이기"},
            ]
        elif consult_url is not None:
            payload["data"] = {"url": consult_url}
            payload["actions"] = [{"action": "open_consult", "title": "불편한 증상이 있어요"}]

        subscriptions = await self._repo.list_web_subscriptions_for_profile(session, profile_id)
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=json.dumps(payload),
                    vapid_private_key=config.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": config.VAPID_CLAIM_EMAIL},
                    # WNS(Windows, notify.windows.com 엔드포인트 - Edge가 이걸 씀)는 이 헤더가
                    # 없으면 400 Bad Request로 조용히 거부한다(pywebpush 2.3.0 기준 자체
                    # 지원 안 함 - https://github.com/web-push-libs/pywebpush/issues/162).
                    # ttl을 안 줘서 기본값 0이므로 "no-cache"를 맞춰준다(ttl>0이면 "cache").
                    # FCM/APNs 등 다른 푸시 서비스는 이 헤더를 그냥 무시하니 안전하다.
                    headers={"X-WNS-Cache-Policy": "no-cache"},
                )
            except WebPushException as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code in (404, 410):
                    # 410 Gone/404 Not Found = 브라우저가 이 구독을 이미 취소/만료시킴.
                    # 서버 DB에만 남아있는 죽은 구독이니 정리한다.
                    await self._repo.delete_by_id(session, sub.id)
                else:
                    logger.warning("웹푸시 발송 실패 (subscription_id=%s): %s", sub.id, exc)

    async def send_to_profile_and_guardians(
        self,
        session: AsyncSession,
        profile_id: int,
        title: str,
        body: str,
        snooze_source: tuple[str, int] | None = None,
        alarm_time: str | None = None,
    ) -> None:
        """`send_to_profile`은 그대로 두고, 여기에 "이 사람을 관리하는 보호자들에게도 같이
        보낸다"는 것만 추가한다. 보호자가 자기 기기에서 "🔔 알림 켜기"를 눌러 구독해두면
        (일반 구독 그대로, 별도의 "가족용 구독" 개념을 새로 안 만듦) 이 프로필이 관리하는
        가족 구성원의 알림도 자동으로 같이 받게 된다.

        보호자가 여러 명을 관리할 수 있어 "누구 약인지" 구분이 안 되면 헷갈리므로, 보호자
        쪽엔 대상자 이름을 붙여서 보낸다(본인 몫은 그대로 둠). snooze_source/alarm_time은
        본인 몫에만 전달한다 - 가족 사본은 스누즈/빈도조정 액션 버튼 없이 정보 전달용으로만
        보낸다."""
        await self.send_to_profile(session, profile_id, title, body, snooze_source=snooze_source, alarm_time=alarm_time)

        guardian_links = await self._family_repo.list_as_member(session, profile_id, status=FamilyLinkStatus.ACCEPTED)
        if not guardian_links:
            return

        member_profile = await self._profile_repo.get_profile(session, profile_id)
        member_name = member_profile.name if member_profile else "가족"
        body_for_guardian = f"[{member_name}] {body}"
        for link in guardian_links:
            await self.send_to_profile(session, link.guardian_profile_id, title, body_for_guardian)
