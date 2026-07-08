from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Self
from uuid import uuid4

from app.core import config
from app.core.jwt.exceptions import ExpiredTokenError, TokenBackendError, TokenBackendExpiredError, TokenError
from app.core.jwt.state import token_backend
from app.models.users import User

if TYPE_CHECKING:
    from app.core.jwt.backends import TokenBackend
    from app.models.profiles import Profile


class Token:
    token_type: str | None = None
    lifetime: timedelta | None = None
    _token_backend: "TokenBackend" = token_backend

    def __init__(self, token: str | None = None, verify: bool = True) -> None:
        if not self.token_type:
            raise TokenError("token_type must be set")
        if not self.lifetime:
            raise TokenError("lifetime must be set")

        self.token = token
        self.current_time = datetime.now(tz=config.TIMEZONE)
        self.payload: dict[str, Any] = {}

        if token is not None:
            try:
                self.payload = token_backend.decode(token, verify=verify)
            except TokenBackendExpiredError as err:
                raise ExpiredTokenError("Token is expired") from err
            except TokenBackendError as err:
                raise TokenError("Token is invalid") from err
        else:
            self.payload = {"type": self.token_type}
            self.set_exp(from_time=self.current_time, lifetime=self.lifetime)
            self.set_jti()

    def __repr__(self) -> str:
        return repr(self.payload)

    def __getitem__(self, key: str):
        return self.payload[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.payload[key] = value

    def __delitem__(self, key: str) -> None:
        del self.payload[key]

    def __contains__(self, key: str) -> Any:
        return key in self.payload

    def __str__(self) -> str:
        """
        Signs and returns a token as a base64 encoded string.
        """
        return self._token_backend.encode(self.payload)

    def set_exp(self, from_time: datetime | None = None, lifetime: timedelta | None = None) -> None:
        if from_time is None:
            from_time = self.current_time

        if lifetime is None:
            lifetime = self.lifetime

        assert lifetime is not None

        dt = from_time + lifetime
        # [T-AUTH-4 버그수정] timegm(dt.timetuple())은 dt의 tzinfo를 무시하고 "이 숫자들이
        # 이미 UTC다"라고 가정한다. config.TIMEZONE이 Asia/Seoul(UTC+9)이라, 실제로는
        # 만료시각이 의도보다 9시간 더 늦게(뒤로) 찍히는 버그가 있었다. dt.timestamp()는
        # tzinfo를 정확히 반영해서 진짜 절대시각(UTC epoch)을 계산한다.
        self.payload["exp"] = int(dt.timestamp())

    def set_jti(self) -> None:
        self.payload["jti"] = uuid4().hex

    @classmethod
    def for_user(cls, user: User) -> Self:
        token = cls()
        token["user_id"] = user.id
        return token

    @classmethod
    def for_user_and_profile(cls, user: User, profile: "Profile") -> Self:
        """토큰에 user_id뿐 아니라 profile_id도 담는다 — 도메인 라우터는 profile_id로 스코핑한다."""
        token = cls.for_user(user)
        token["profile_id"] = profile.id
        return token


class AccessToken(Token):
    token_type = "access"
    lifetime = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)


class RefreshToken(Token):
    token_type = "refresh"
    # [T-AUTH-4 버그수정] 예전엔 timedelta(days=...)였는데, REFRESH_TOKEN_EXPIRE_MINUTES는
    # "분" 단위 값(20160=14일)이라 실제로는 20160일(약 55년)짜리 토큰이 발급되고 있었다.
    lifetime = timedelta(minutes=config.REFRESH_TOKEN_EXPIRE_MINUTES)
    no_copy_claims = ("type", "exp", "jti")

    @property
    def access_token(self) -> AccessToken:
        access = AccessToken()
        access.set_exp(from_time=self.current_time)

        no_copy = self.no_copy_claims
        for claim, value in self.payload.items():
            if claim in no_copy:
                continue
            access[claim] = value

        return access


class PendingSocialSignupToken(Token):
    """[T-AUTH-7 동의 순서 수정] 소셜 로그인 콜백 시점엔 아직 계정을 만들지 않는다.
    개인정보보호법상 "동의 먼저, 수집(=DB 저장)은 그다음"이 원칙이라, 제공자가 넘겨준
    프로필 정보를 여기 임시로 서명해서 담아두고, 사용자가 우리 서비스 약관에 동의를 완료한
    순간에만(POST /auth/{provider}/complete-signup) 진짜 User+Profile을 생성한다.
    User 객체가 아직 없는 상태라 for_user()를 쓸 수 없어서 별도 클래스로 뺐다."""

    token_type = "pending_social_signup"
    lifetime = timedelta(minutes=10)

    @classmethod
    def for_social_profile(cls, provider: str, sns_id: str, email: str | None, name: str | None) -> Self:
        token = cls()
        token["provider"] = provider
        token["sns_id"] = sns_id
        token["email"] = email
        token["name"] = name
        return token
