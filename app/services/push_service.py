import json
import logging

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import credentials, messaging
from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.family_link import FamilyLinkStatus
from app.models.push_subscription import PushPlatform
from app.repositories.family_repository import FamilyRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.push_subscription_repository import PushSubscriptionRepository

logger = logging.getLogger("app.push_service")

_firebase_app: firebase_admin.App | None = None
_firebase_init_attempted = False


def _get_firebase_app() -> firebase_admin.App | None:
    """FIREBASE_CREDENTIALS_PATH가 설정돼 있으면 firebase_admin 앱을 프로세스당 한 번만
    초기화해서 재사용한다. 미설정이거나 초기화가 실패하면(파일 없음/형식 오류 등) None을
    반환하고, 호출부는 iOS/Android 발송만 조용히 건너뛴다(웹푸시는 영향 없음)."""
    global _firebase_app, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True
    if not config.FIREBASE_CREDENTIALS_PATH:
        return None
    try:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
    except Exception:
        logger.exception("Firebase Admin SDK 초기화 실패 - FCM 발송을 건너뜁니다.")
        _firebase_app = None
    return _firebase_app


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

    async def subscribe_native(
        self, session: AsyncSession, profile_id: int, platform: PushPlatform, device_token: str
    ) -> None:
        """iOS/Android 앱이 발급받은 FCM 디바이스 토큰을 등록한다. subscribe()의 웹푸시
        재구독 로직과 같은 이유로, 이미 등록된 토큰이면 profile_id만 갱신한다(같은 기기에서
        로그아웃 후 다른 계정으로 로그인한 경우)."""
        existing = await self._repo.get_by_device_token(session, device_token)
        if existing:
            if existing.profile_id != profile_id:
                await self._repo.update_profile_id(session, existing.id, profile_id)
            return
        await self._repo.create_native(session, profile_id, platform, device_token)

    async def unsubscribe_native(self, session: AsyncSession, device_token: str) -> None:
        await self._repo.delete_by_device_token(session, device_token)

    async def send_to_profile(self, session: AsyncSession, profile_id: int, title: str, body: str) -> None:
        """이 프로필이 구독해둔 모든 기기(WEB=웹푸시, IOS/ANDROID=FCM)에 푸시를 보낸다.
        구독 하나가 실패해도(예: 브라우저에서 구독 취소했는데 서버 DB에는 아직 남아있는
        경우) 나머지 기기 발송은 계속한다."""
        await self._send_to_web_subscriptions(session, profile_id, title, body)
        await self._send_to_native_subscriptions(session, profile_id, title, body)

    async def _send_to_web_subscriptions(
        self, session: AsyncSession, profile_id: int, title: str, body: str
    ) -> None:
        if not config.VAPID_PRIVATE_KEY:
            logger.warning("VAPID 비밀키가 설정되지 않아 웹푸시 발송을 건너뜁니다.")
            return

        subscriptions = await self._repo.list_web_subscriptions_for_profile(session, profile_id)
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=json.dumps({"title": title, "body": body}),
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

    async def _send_to_native_subscriptions(
        self, session: AsyncSession, profile_id: int, title: str, body: str
    ) -> None:
        firebase_app = _get_firebase_app()
        if firebase_app is None:
            return

        subscriptions = await self._repo.list_native_subscriptions_for_profile(session, profile_id)
        for sub in subscriptions:
            if not sub.device_token:
                continue
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    token=sub.device_token,
                )
                messaging.send(message, app=firebase_app)
            except messaging.UnregisteredError:
                # 앱 삭제/토큰 만료 등으로 더 이상 유효하지 않은 토큰 - DB에서 정리한다
                # (웹푸시의 404/410 Gone과 같은 의미).
                await self._repo.delete_by_id(session, sub.id)
            except Exception:
                logger.exception("FCM 발송 실패 (subscription_id=%s)", sub.id)

    async def send_to_profile_and_guardians(
        self, session: AsyncSession, profile_id: int, title: str, body: str
    ) -> None:
        """`send_to_profile`은 그대로 두고, 여기에 "이 사람을 관리하는 보호자들에게도 같이
        보낸다"는 것만 추가한다. 보호자가 자기 기기에서 "🔔 알림 켜기"를 눌러 구독해두면
        (일반 구독 그대로, 별도의 "가족용 구독" 개념을 새로 안 만듦) 이 프로필이 관리하는
        가족 구성원의 알림도 자동으로 같이 받게 된다.

        보호자가 여러 명을 관리할 수 있어 "누구 약인지" 구분이 안 되면 헷갈리므로, 보호자
        쪽엔 대상자 이름을 붙여서 보낸다(본인 몫은 그대로 둠)."""
        await self.send_to_profile(session, profile_id, title, body)

        guardian_links = await self._family_repo.list_as_member(session, profile_id, status=FamilyLinkStatus.ACCEPTED)
        if not guardian_links:
            return

        member_profile = await self._profile_repo.get_profile(session, profile_id)
        member_name = member_profile.name if member_profile else "가족"
        body_for_guardian = f"[{member_name}] {body}"
        for link in guardian_links:
            await self.send_to_profile(session, link.guardian_profile_id, title, body_for_guardian)
