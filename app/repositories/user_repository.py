from datetime import date, datetime
from typing import Any

from pydantic import EmailStr

from app.core import config
from app.models.users import Gender, User

ALLOWED_UPDATE_FIELDS = ["name", "phone_number", "gender", "birthday"]
UPDATED_AT_FIELD = "updated_at"


class UserRepository:
    def __init__(self):
        self._model = User

    async def get_all(self):
        return await self._model.all()

    async def get_user(self, user_id: int) -> User | None:
        return await self._model.get_or_none(id=user_id)

    async def create_user(
        self,
        email: str | EmailStr,
        hashed_password: str,
        name: str,
        phone_number: str,
        gender: Gender,
        birthday: date,
        *,
        is_active: bool = True,
        is_admin: bool = False,
        agreed_terms_at: datetime | None = None,
    ) -> User:
        return await self._model.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
            phone_number=phone_number,
            gender=gender,
            birthday=birthday,
            is_active=is_active,
            is_admin=is_admin,
            agreed_terms_at=agreed_terms_at,
        )

    async def get_user_by_email(self, email: str) -> User | None:
        return await self._model.get_or_none(email=email)

    async def exists_by_email(self, email: str) -> bool:
        return await self._model.filter(email=email).exists()

    async def exists_by_phone_number(self, phone_number: str) -> bool:
        return await self._model.filter(phone_number=phone_number).exists()

    async def update_last_login(self, user_id: int) -> None:
        await self._model.filter(id=user_id).update(last_login=datetime.now(config.TIMEZONE))

    # [핀포인트 추가] Refresh Token 회전/로그아웃 지원
    async def update_refresh_token(self, user_id: int, refresh_token: str | None) -> None:
        await self._model.filter(id=user_id).update(refresh_token=refresh_token)

    async def get_by_valid_refresh_token(self, user_id: int, refresh_token: str) -> User | None:
        """DB에 저장된 refresh_token과 넘어온 값이 정확히 일치할 때만 사용자를 반환합니다.
        (로그아웃했거나 이미 한 번 회전되어 무효화된 토큰은 여기서 걸러집니다.)"""
        return await self._model.get_or_none(id=user_id, refresh_token=refresh_token)

    # [핀포인트 추가] 소셜 로그인 (구글/네이버/카카오)
    async def get_by_sns(self, provider: str, sns_id: str) -> User | None:
        return await self._model.get_or_none(sns_provider=provider, sns_id=sns_id)

    async def link_sns_to_existing_user(self, user: User, provider: str, sns_id: str) -> None:
        user.sns_provider = provider
        user.sns_id = sns_id
        await user.save(update_fields=["sns_provider", "sns_id"])

    async def create_social_user(self, email: str, hashed_password: str, name: str, provider: str, sns_id: str) -> User:
        # [주의] hashed_password는 본인만 아는 값이 아니라 사용 불가능한 임의 문자열을 해시한 것입니다.
        # (기존 hashed_password 컬럼이 NOT NULL이라 값을 채워야 해서 임시 처리)
        return await self._model.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
            phone_number="",
            gender=Gender.MALE,  # 소셜 제공자가 성별을 안 주는 경우가 많아 임시값, 로그인 후 /users/me에서 수정 유도
            birthday=date(2000, 1, 1),
            sns_provider=provider,
            sns_id=sns_id,
        )

    async def update_instance(self, user: User, data: dict[str, Any]) -> None:
        update_fields = []
        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)
                update_fields.append(key)
        if update_fields:
            user.updated_at = datetime.now(config.TIMEZONE)
            update_fields.append(UPDATED_AT_FIELD)
            await user.save(update_fields=update_fields)
