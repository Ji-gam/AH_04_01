from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.common import normalize_phone_number
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import LoginRequest, SignUpRequest
from app.models.profiles import Profile, ProfileRelation
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.profile_repo = ProfileRepository()
        self.jwt_service = JwtService()

    async def signup(self, session: AsyncSession, data: SignUpRequest) -> tuple[User, Profile]:
        # 이메일 중복 체크
        await self.check_email_exists(session, data.email)

        # 입력받은 휴대폰 번호를 노말라이즈
        normalized_phone_number = normalize_phone_number(data.phone_number)

        # 휴대폰 번호 중복 체크
        await self.check_phone_number_exists(session, normalized_phone_number)

        # 계정(User) 생성 + 본인 프로필(Profile, relation=SELF) 생성을 한 트랜잭션으로 묶는다
        # (앞선 중복확인 SELECT로 세션에 트랜잭션이 이미 자동 시작돼 있으므로, 여기서는 commit만 한다)
        user = await self.user_repo.create_user(
            session,
            email=data.email,
            hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
        )
        profile = await self.profile_repo.create_profile(
            session,
            user_id=user.id,
            name=data.name,
            phone_number=normalized_phone_number,
            gender=data.gender,
            birthday=data.birth_date,
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

        # 비밀번호 검증
        if not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 활성 사용자 체크
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="비활성화된 계정입니다.")

        return user

    async def login(self, session: AsyncSession, user: User) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(session, user.id)
        profile = await self.profile_repo.get_default_profile_for_user(session, user.id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="프로필을 찾을 수 없습니다.")
        await session.commit()
        return self.jwt_service.issue_jwt_pair(user, profile)

    async def check_email_exists(self, session: AsyncSession, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(session, email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

    async def check_phone_number_exists(self, session: AsyncSession, phone_number: str) -> None:
        if await self.profile_repo.exists_by_phone_number(session, phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")
