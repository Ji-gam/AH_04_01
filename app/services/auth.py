from datetime import UTC, datetime

from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from starlette import status
from tortoise.transactions import in_transaction

from app.dtos.auth import LoginRequest, SignUpRequest
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService
from app.core.utils.common import normalize_phone_number
from app.core.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.security import hash_password, verify_password


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.jwt_service = JwtService()

    async def signup(self, data: SignUpRequest) -> User:
        # 이메일 중복 체크
        await self.check_email_exists(data.email)

        # 입력받은 휴대폰 번호를 노말라이즈
        normalized_phone_number = normalize_phone_number(data.phone_number)

        # 휴대폰 번호 중복 체크
        await self.check_phone_number_exists(normalized_phone_number)

        # 유저 생성
        # [핀포인트 추가] DTO 검증(_validate_agreed_terms)을 이미 통과했으므로 data.agreed_terms는
        # 항상 True입니다. "언제" 동의했는지 증빙용으로 지금 시각을 저장합니다.
        async with in_transaction():
            user = await self.user_repo.create_user(
                email=data.email,
                hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
                name=data.name,
                phone_number=normalized_phone_number,
                gender=data.gender,
                birthday=data.birth_date,
                agreed_terms_at=datetime.now(UTC),
            )

            return user

    async def authenticate(self, data: LoginRequest) -> User:
        # 이메일로 사용자 조회
        email = str(data.email)
        user = await self.user_repo.get_user_by_email(email)
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

    async def login(self, user: User) -> dict[str, AccessToken | RefreshToken]:
        await self.user_repo.update_last_login(user.id)
        tokens = self.jwt_service.issue_jwt_pair(user)
        # [핀포인트 추가] 발급한 refresh_token을 DB에도 저장 (나중에 회전/로그아웃 검증에 사용)
        await self.user_repo.update_refresh_token(user.id, str(tokens["refresh_token"]))
        return tokens

    async def rotate_refresh_token(self, refresh_token: str) -> dict[str, AccessToken | RefreshToken]:
        """[핀포인트 추가] 토큰 재발급 시, Access뿐 아니라 Refresh도 새로 발급하고
        DB에 저장된 예전 값을 즉시 새 값으로 덮어써서 무효화합니다.
        (탈취된 refresh_token이 있어도, 정상 사용자가 한 번 더 갱신하면 그 순간 탈취분은 못 쓰게 됩니다.)"""
        verified_rt = self.jwt_service.verify_jwt(token=refresh_token, token_type="refresh")
        user_id = verified_rt.payload["user_id"]

        user = await self.user_repo.get_by_valid_refresh_token(user_id, refresh_token)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 리프레시 토큰입니다.")

        new_rt = self.jwt_service.create_refresh_token(user)
        new_at = new_rt.access_token
        await self.user_repo.update_refresh_token(user.id, str(new_rt))
        return {"access_token": new_at, "refresh_token": new_rt}

    async def logout(self, user: User) -> None:
        """[핀포인트 추가] DB의 refresh_token을 비워서, 갖고 있던 쿠키가 더 이상 안 먹히게 만듭니다."""
        await self.user_repo.update_refresh_token(user.id, None)

    async def check_email_exists(self, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

    async def check_phone_number_exists(self, phone_number: str) -> None:
        if await self.user_repo.exists_by_phone_number(phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")
