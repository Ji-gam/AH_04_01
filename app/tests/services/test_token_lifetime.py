"""
[T-AUTH-4 버그수정] RefreshToken 만료시간 검증.
예전엔 timedelta(days=REFRESH_TOKEN_EXPIRE_MINUTES)로 계산되어, 20160(분 단위 값)이
그대로 "일"로 들어가서 약 55년짜리 토큰이 발급되고 있었다. 정확히 설정값(분)만큼만
유효해야 한다는 걸 이 테스트로 못박는다.
"""

from datetime import datetime, timedelta

from app.core import config
from app.core.jwt.tokens import RefreshToken
from app.models.users import User


def test_refresh_token_lifetime_is_minutes_not_days():
    """RefreshToken.lifetime 자체가 분 단위로 정확히 설정되어 있어야 한다."""
    assert RefreshToken.lifetime == timedelta(minutes=config.REFRESH_TOKEN_EXPIRE_MINUTES)
    # 회귀 방지: 실수로 다시 days=...로 바뀌면 14일이 아니라 20160일이 되어 이 값이 완전히 달라진다.
    assert RefreshToken.lifetime == timedelta(days=14)


def test_refresh_token_exp_is_about_14_days_not_55_years():
    """실제 발급된 토큰의 만료 시각이 지금으로부터 대략 14일 뒤여야 한다 (55년 뒤가 아니라)."""
    user = User(id=1, email="lifetime_test@example.com", hashed_password="x")
    token = RefreshToken.for_user(user)

    now_ts = datetime.now(tz=config.TIMEZONE).timestamp()
    seconds_until_expiry = token.payload["exp"] - now_ts

    fourteen_days_in_seconds = 14 * 24 * 60 * 60
    one_year_in_seconds = 365 * 24 * 60 * 60

    # 14일 근처(오차 1시간 허용)인지 확인 - 55년짜리였다면 이 assert가 바로 실패한다.
    assert abs(seconds_until_expiry - fourteen_days_in_seconds) < 3600
    assert seconds_until_expiry < one_year_in_seconds
