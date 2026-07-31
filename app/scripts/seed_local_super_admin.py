"""로컬 전용 슈퍼관리자 자동 시딩.

`ENV=local`이고 `.env`에 `LOCAL_SUPER_ADMIN_EMAIL`/`LOCAL_SUPER_ADMIN_PASSWORD`가
둘 다 채워져 있을 때만, 서버 기동 시(app/main.py의 lifespan) 자동으로 계정을 만들고
관리자로 지정한다. 매번 `docker compose down -v` 등으로 로컬 DB가 초기화될 때마다
"회원가입 → app/scripts/promote_admin.py 실행"을 반복하지 않아도 되게 하기 위함
(관리자 화면 로컬 테스트가 어렵다는 요청으로 추가).

## 안전장치 (2중)
1. `ENV=local`이 아니면 아예 실행되지 않는다(다른 LOCAL 전용 기능 - app/admin.py의
   DB 뷰어 - 와 같은 게이팅 패턴).
2. 위 두 환경변수 중 하나라도 없으면 아무 일도 안 일어난다 - 코드에 실제 로그인
   정보를 하드코딩하지 않는다. 이 값들은 dev/prod `.env`에는 아예 넣지 않는 것으로
   운영 환경 노출을 원천 차단한다(1번 게이팅이 뚫리는 경우에 대비한 2차 방어선).

이미 같은 이메일로 가입된 계정이 있으면 새로 안 만들고, 관리자가 아니면 승격만
한다(여러 번 기동해도 안전 - 멱등).
"""

import logging
from datetime import datetime

from app.core import config
from app.core.config import Env
from app.core.db.databases import AsyncSessionLocal
from app.dtos.auth import SignUpRequest
from app.repositories.user_repository import UserRepository
from app.services.auth import AuthService

logger = logging.getLogger("app.seed_local_super_admin")


async def seed_local_super_admin() -> None:
    if config.ENV != Env.LOCAL:
        return
    email = config.LOCAL_SUPER_ADMIN_EMAIL
    password = config.LOCAL_SUPER_ADMIN_PASSWORD
    if not email or not password:
        return

    async with AsyncSessionLocal() as session:
        user_repo = UserRepository()
        existing = await user_repo.get_user_by_email(session, email)
        if existing is not None:
            if not existing.is_admin:
                existing.is_admin = True
                await session.commit()
                logger.info("[로컬 시딩] 기존 계정을 관리자로 승격했습니다: %s", email)
            return

        auth_service = AuthService()
        user, _profile = await auth_service.signup(
            session, SignUpRequest(email=email, password=password, name="슈퍼관리자")
        )
        user.is_admin = True
        # 로컬 테스트 편의 목적 - 매번 통합동의 화면부터 다시 누르지 않아도 되게
        # 필수 동의 3종을 가입과 동시에 완료 처리한다(실제 서비스 동의 흐름과는
        # 별개, 이 계정에 한해서만).
        now = datetime.now(tz=config.TIMEZONE)
        user.health_info_consented_at = now
        user.ai_chat_consented_at = now
        user.terms_of_service_consented_at = now
        await session.commit()
        logger.info("[로컬 시딩] 슈퍼관리자 계정을 새로 만들었습니다: %s", email)
