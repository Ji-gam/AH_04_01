"""
TDD 규칙 (CODING_RULES.md 4번):
- Service 함수 하나당 최소 2개 테스트: '정상 케이스' + '실패/경계 케이스'
- 단위테스트는 진짜 DB를 쓰지 않는다.

참고: OAuthService.handle_callback()은 AuthService.signup()과 동일하게
Repository를 생성자에서 직접 만들어 쓰는 기존 패턴을 따르고 있어(DI 아님),
sample_code_chat의 FakeRepository 주입 패턴을 그대로 적용하긴 어렵다.
이 파일은 그중 순수 로직(외부 상태 없음)인 build_authorize_url만 단위테스트하고,
handle_callback의 DB 관련 경로는 app/tests/auth_apis/test_oauth_login.py의
Router 통합테스트(실제 테스트 DB 사용)로 커버한다.
"""

import pytest
from fastapi import HTTPException

from app.services.oauth import OAuthService


def test_build_authorize_url_returns_valid_google_url():
    service = OAuthService()

    url = service.build_authorize_url("google")

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "response_type=code" in url


def test_build_authorize_url_rejects_unsupported_provider():
    service = OAuthService()

    with pytest.raises(HTTPException) as exc_info:
        service.build_authorize_url("facebook")

    assert exc_info.value.status_code == 404
