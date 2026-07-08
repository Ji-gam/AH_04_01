from typing import Literal, overload

from fastapi import HTTPException

from app.core.jwt.exceptions import ExpiredTokenError, TokenError
from app.core.jwt.tokens import AccessToken, PendingSocialSignupToken, RefreshToken
from app.models.profiles import Profile
from app.models.users import User


class JwtService:
    access_token_class = AccessToken
    refresh_token_class = RefreshToken

    def create_access_token(self, user: User, profile: Profile) -> AccessToken:
        return self.access_token_class.for_user_and_profile(user, profile)

    def create_refresh_token(self, user: User, profile: Profile) -> RefreshToken:
        return self.refresh_token_class.for_user_and_profile(user, profile)

    @overload
    def verify_jwt(
        self,
        token: str,
        token_type: Literal["access"],
    ) -> AccessToken: ...

    @overload
    def verify_jwt(
        self,
        token: str,
        token_type: Literal["refresh"],
    ) -> RefreshToken: ...

    def verify_jwt(self, token: str, token_type: Literal["access", "refresh"]) -> AccessToken | RefreshToken:
        token_class: type[AccessToken | RefreshToken]
        if token_type == "access":
            token_class = self.access_token_class
        else:
            token_class = self.refresh_token_class

        try:
            verified = token_class(token=token)
            return verified
        except ExpiredTokenError as err:
            raise HTTPException(status_code=401, detail=f"{token_type} token has expired.") from err
        except TokenError as err:
            raise HTTPException(status_code=400, detail="Provided invalid token.") from err

    def refresh_jwt(self, refresh_token: str) -> AccessToken:
        verified_rt = self.verify_jwt(token=refresh_token, token_type="refresh")
        return verified_rt.access_token

    def issue_jwt_pair(self, user: User, profile: Profile) -> dict[str, AccessToken | RefreshToken]:
        rt = self.create_refresh_token(user, profile)
        at = rt.access_token
        return {"access_token": at, "refresh_token": rt}

    def verify_pending_social_signup(self, token: str) -> PendingSocialSignupToken:
        """[T-AUTH-7] 소셜 가입 완료(POST /auth/{provider}/complete-signup)에서 쓴다."""
        try:
            return PendingSocialSignupToken(token=token)
        except ExpiredTokenError as err:
            raise HTTPException(
                status_code=401, detail="가입 대기 시간이 만료되었습니다. 소셜 로그인을 다시 시도해주세요."
            ) from err
        except TokenError as err:
            raise HTTPException(status_code=400, detail="유효하지 않은 가입 대기 토큰입니다.") from err
