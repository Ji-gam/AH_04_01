from datetime import datetime, timedelta

from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from app.core import config
from app.core.jwt.exceptions import TokenError
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import LoginRequest, SignUpRequest
from app.models.profiles import Profile, ProfileRelation
from app.models.users import User
from app.models.withdrawn_stats import WithdrawnHealthStat
from app.repositories.profile_repository import ProfileRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.age_calculator import age_group
from app.services.jwt import JwtService

# [로그인 시도 제한] 브루트포스(비밀번호 무차별 대입) 방어 - OWASP 권장 방식.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.profile_repo = ProfileRepository()
        self.refresh_token_repo = RefreshTokenRepository()
        self.jwt_service = JwtService()

    async def signup(self, session: AsyncSession, data: SignUpRequest) -> tuple[User, Profile]:
        # 이메일 중복 체크
        await self.check_email_exists(session, data.email)

        # 계정(User) 생성 + 본인 프로필(Profile, relation=SELF) 생성을 한 트랜잭션으로 묶는다
        # (앞선 중복확인 SELECT로 세션에 트랜잭션이 이미 자동 시작돼 있으므로, 여기서는 commit만 한다)
        # [가입 최소화] 성별/나이/휴대폰번호는 여기서 안 받는다 - 더보기 > 개인건강정보에서 나중에 채운다.
        user = await self.user_repo.create_user(
            session,
            email=data.email,
            hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
        )
        profile = await self.profile_repo.create_profile(
            session,
            user_id=user.id,
            name=data.name,
            relation=ProfileRelation.SELF,
        )
        await session.commit()

        return user, profile

    async def authenticate(self, session: AsyncSession, data: LoginRequest) -> User:
        # 이메일로 사용자 조회
        email = str(data.email)
        user = await self.user_repo.get_user_by_email(session, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # [로그인 시도 제한] 이미 잠긴 상태면 비밀번호 확인 자체를 안 하고 바로 막는다.
        now = datetime.now(tz=config.TIMEZONE)
        # MySQL(asyncmy)은 DATETIME 컬럼을 다시 읽어올 때 타임존 정보 없이(naive) 돌려준다 -
        # Python에서 계산해서 저장했던 tz-aware 값과 비교하면 TypeError가 나므로, 비교 전에
        # naive면 같은 타임존을 붙여서 맞춰준다.
        locked_until = user.locked_until
        if locked_until is not None and locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=config.TIMEZONE)
        if locked_until is not None and locked_until > now:
            remaining_minutes = max(1, int((locked_until - now).total_seconds() // 60) + 1)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"로그인 시도 횟수를 초과해 계정이 잠겼습니다. {remaining_minutes}분 후 다시 시도해주세요.",
            )

        # 비밀번호 검증 (소셜 가입자는 hashed_password가 없다 - 이메일/비번 로그인 자체가 대상이 아니므로 동일한 에러로 막는다)
        if user.hashed_password is None or not verify_password(data.password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + LOCKOUT_DURATION
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 로그인 성공 - 실패 카운터/잠금 상태 초기화
        user.failed_login_attempts = 0
        user.locked_until = None
        await session.commit()

        # 활성 사용자 체크
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="비활성화된 계정입니다.")

        return user

    async def login(self, session: AsyncSession, user: User) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(session, user.id)
        profile = await self.profile_repo.get_default_profile_for_user(session, user.id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다.")
        tokens = self.jwt_service.issue_jwt_pair(user, profile)
        # [리프레시 토큰 로테이션] 새로 발급한 리프레시 토큰의 jti를 추적 테이블에 남긴다 -
        # 나중에 이 토큰으로 갱신 시도가 오면 이 레코드를 보고 로테이션/재사용 탐지를 한다.
        refresh_token = tokens["refresh_token"]
        await self.refresh_token_repo.create(session, user.id, refresh_token.payload["jti"])
        await session.commit()
        return tokens

    async def logout(self, session: AsyncSession, refresh_token_str: str) -> None:
        """로그아웃 - refresh_token을 revoke해서 재사용 못하게 한다. 로그아웃은 사용자 입장에서
        항상 성공해야 하므로(토큰이 이미 만료/위조됐어도), 검증 실패는 조용히 무시한다."""
        try:
            verified_rt = self.jwt_service.verify_jwt(token=refresh_token_str, token_type="refresh")
        except TokenError:
            return
        jti = verified_rt.payload["jti"]
        await self.refresh_token_repo.revoke(session, jti)
        await session.commit()

    async def rotate_refresh_token(
        self, session: AsyncSession, refresh_token_str: str
    ) -> dict[str, AccessToken | RefreshToken]:
        """[리프레시 토큰 로테이션 + 재사용 탐지] 토큰 갱신할 때마다 리프레시 토큰 자체를
        새 값으로 교체하고, 방금 쓴 토큰은 즉시 무효화한다. 만약 이미 무효화된(예전) 토큰이
        다시 사용되면 - 이는 토큰이 탈취되어 공격자와 정상 사용자가 각자 따로 쓰고 있다는
        신호이므로 - 해당 계정의 모든 세션을 즉시 강제 로그아웃시킨다."""
        verified_rt = self.jwt_service.verify_jwt(token=refresh_token_str, token_type="refresh")
        jti = verified_rt.payload["jti"]

        record = await self.refresh_token_repo.get_by_jti(session, jti)
        if record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")

        if record.is_revoked:
            await self.refresh_token_repo.revoke_all_for_user(session, record.user_id)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 재사용이 감지되어 모든 세션이 로그아웃되었습니다. 다시 로그인해주세요.",
            )

        await self.refresh_token_repo.revoke(session, jti)

        new_refresh_token = RefreshToken()
        new_refresh_token["user_id"] = verified_rt.payload["user_id"]
        new_refresh_token["profile_id"] = verified_rt.payload["profile_id"]
        await self.refresh_token_repo.create(session, verified_rt.payload["user_id"], new_refresh_token.payload["jti"])
        await session.commit()

        return {"access_token": new_refresh_token.access_token, "refresh_token": new_refresh_token}

    async def check_email_exists(self, session: AsyncSession, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(session, email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

    async def check_phone_number_exists(self, session: AsyncSession, phone_number: str) -> None:
        if await self.profile_repo.exists_by_phone_number(session, phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")

    async def withdraw(self, session: AsyncSession, user: User, password: str | None) -> None:
        """회원탈퇴. 개인정보보호법상 탈퇴 시 지체없이 파기해야 하므로 소프트삭제가 아니라
        즉시 완전 삭제한다. User를 지우면 Profile도 cascade(delete-orphan)로 같이 삭제된다.

        [2026-07-28 수정] 원래 "소셜 가입자는 비밀번호가 없다 - 이 메서드는 아직 이메일
        가입자 전용이다(소셜 탈퇴는 다음 단계에서 다룬다)"는 상태로 남아있어서, 소셜
        가입자는 사실상 탈퇴가 불가능했다(hashed_password가 항상 None이라 검증을 항상
        실패함). 소셜 계정은 비밀번호 재확인 없이(유효한 토큰만으로) 탈퇴 가능하게 풀었다 -
        OAuth 재인증까지 요구하는 더 엄격한 방식은 범위 밖으로 남겨둔다.

        [익명화 통계] 완전 삭제 전에, 진단병력/가족력을 식별정보 없이 통계용으로 남긴다
        (WithdrawnHealthStat - profile_id/user_id/이름 등 전혀 안 남고, 나이도 나이대로
        일반화). 개인정보보호법 제28조의2(가명정보의 통계작성 목적 처리)에 근거 - 팀 논의
        내용은 withdraw_data_policy_summary.md 참고. 탈퇴 안내 문구에도 "통계 목적으로
        익명처리된 형태로만 일부 남을 수 있다"고 명시한다."""
        if user.hashed_password is not None:
            if password is None or not verify_password(password, user.hashed_password):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비밀번호가 올바르지 않습니다.")
        # else: 소셜 가입자 - 비밀번호 자체가 없으므로 검증 없이 진행(유효한 토큰만으로 탈퇴 허용)

        result = await session.execute(
            select(Profile)
            .where(Profile.user_id == user.id)
            .options(selectinload(Profile.diagnosis_entries), selectinload(Profile.family_history_entries))
        )
        profiles = result.scalars().all()
        for profile in profiles:
            group = age_group(profile.birth_date)
            for diagnosis in profile.diagnosis_entries:
                session.add(
                    WithdrawnHealthStat(
                        disease=diagnosis.disease, is_family_history=False, age_group=group, gender=profile.gender
                    )
                )
            for family_entry in profile.family_history_entries:
                session.add(
                    WithdrawnHealthStat(
                        disease=family_entry.disease,
                        is_family_history=True,
                        age_group=group,
                        gender=profile.gender,
                    )
                )

        await session.delete(user)
        await session.commit()
