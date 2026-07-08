# app/core/oauth/providers.py
# 구글/네이버/카카오 3사의 OAuth 엔드포인트와 프로필 파싱 방식을 정의한다.
# 실제 Client ID/Secret이 오면 .env에 값만 채우면 되고, 이 파일은 안 건드려도 된다.
from app.core import config


def get_provider_config(provider: str) -> dict | None:
    configs = {
        "google": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "scope": "openid email profile",
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
        },
        "naver": {
            "authorize_url": "https://nid.naver.com/oauth2.0/authorize",
            "token_url": "https://nid.naver.com/oauth2.0/token",
            "userinfo_url": "https://openapi.naver.com/v1/nid/me",
            "scope": "",
            "client_id": config.NAVER_CLIENT_ID,
            "client_secret": config.NAVER_CLIENT_SECRET,
            "redirect_uri": config.NAVER_REDIRECT_URI,
        },
        "kakao": {
            "authorize_url": "https://kauth.kakao.com/oauth/authorize",
            "token_url": "https://kauth.kakao.com/oauth/token",
            "userinfo_url": "https://kapi.kakao.com/v2/user/me",
            "scope": "",
            "client_id": config.KAKAO_CLIENT_ID,
            "client_secret": config.KAKAO_CLIENT_SECRET,
            "redirect_uri": config.KAKAO_REDIRECT_URI,
        },
    }
    return configs.get(provider)


def normalize_userinfo(provider: str, raw: dict) -> dict:
    """3사마다 응답 형태가 전부 달라서, 공통 형태 {sns_id, email, name}으로 통일한다."""
    if provider == "google":
        return {"sns_id": raw.get("sub"), "email": raw.get("email"), "name": raw.get("name")}
    if provider == "naver":
        body = raw.get("response", {})
        return {"sns_id": body.get("id"), "email": body.get("email"), "name": body.get("name")}
    if provider == "kakao":
        account = raw.get("kakao_account", {})
        profile = account.get("profile", {})
        # [임시조치][TODO] 지금은 "정식 앱(비즈니스 앱 전환 + 검수)"이 아니라서, 카카오
        # 콘솔에서 이메일 동의단계를 "필수 동의"가 아니라 "선택 동의"로 낮춰서 받고 있다
        # (필수 동의는 비즈니스 앱 전환 + 카카오 검수가 있어야만 설정 가능). 선택 동의라
        # 사용자가 거부하면 email이 None으로 온다 - 그 경우 OAuthService가 임시 이메일
        # (kakao_{sns_id}@social.remedi.local)을 자동 생성해서 채운다.
        # 정식 서비스 출시 시점에 비즈니스 앱 전환 + 검수를 마치고, 콘솔에서 이메일을
        # "필수 동의"로 올려서 이 임시 이메일 생성 로직이 실제로는 안 타게 만들어야 한다.
        return {
            "sns_id": str(raw.get("id")) if raw.get("id") is not None else None,
            "email": account.get("email"),
            "name": profile.get("nickname"),
        }
    raise ValueError(f"지원하지 않는 provider: {provider}")
