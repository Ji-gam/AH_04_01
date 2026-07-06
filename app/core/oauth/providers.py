# app/core/oauth/providers.py
# [핀포인트 추가] 구글/네이버/카카오 3사의 OAuth 엔드포인트와 프로필 파싱 방식을 정의합니다.
# 실제 Client ID/Secret이 오면 .env에 값만 채우면 되고, 이 파일은 안 건드려도 됩니다.
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
        },
        "naver": {
            "authorize_url": "https://nid.naver.com/oauth2.0/authorize",
            "token_url": "https://nid.naver.com/oauth2.0/token",
            "userinfo_url": "https://openapi.naver.com/v1/nid/me",
            "scope": "",
            "client_id": config.NAVER_CLIENT_ID,
            "client_secret": config.NAVER_CLIENT_SECRET,
        },
        "kakao": {
            "authorize_url": "https://kauth.kakao.com/oauth/authorize",
            "token_url": "https://kauth.kakao.com/oauth/token",
            "userinfo_url": "https://kapi.kakao.com/v2/user/me",
            "scope": "",
            "client_id": config.KAKAO_CLIENT_ID,
            "client_secret": config.KAKAO_CLIENT_SECRET,
        },
    }
    return configs.get(provider)


def normalize_userinfo(provider: str, raw: dict) -> dict:
    """3사마다 응답 형태가 전부 달라서, 공통 형태 {sns_id, email, name}으로 통일합니다."""
    if provider == "google":
        return {"sns_id": raw.get("sub"), "email": raw.get("email"), "name": raw.get("name")}
    if provider == "naver":
        body = raw.get("response", {})
        return {"sns_id": body.get("id"), "email": body.get("email"), "name": body.get("name")}
    if provider == "kakao":
        account = raw.get("kakao_account", {})
        profile = account.get("profile", {})
        return {
            "sns_id": str(raw.get("id")) if raw.get("id") is not None else None,
            "email": account.get("email"),
            "name": profile.get("nickname"),
        }
    raise ValueError(f"지원하지 않는 provider: {provider}")
