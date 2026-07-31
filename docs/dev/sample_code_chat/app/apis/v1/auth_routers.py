"""
Router 레이어 규칙:
- 여기는 오직 'HTTP 요청을 받아서 Service를 부르고, 그 결과를 HTTP 응답으로 바꾸는 것'만 한다.
- 여기서 절대 하면 안 되는 것: 비즈니스 판단(if문으로 조건 분기), DB 접근
- 이 규칙 하나만 지켜도, 나중에 앱 형태가 바뀌어도(웹→모바일 API 재사용 등) Service는 그대로 재사용 가능하다.
실제 위치: app/apis/v1/auth_routers.py (레이어 우선 구조, CODING_RULES.md 2번)
"""

from fastapi import APIRouter

from app.dtos.auth import NicknameCheckResponse
from app.services.nickname_service import NicknameService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/nickname/check", response_model=NicknameCheckResponse)
def check_nickname(nickname: str) -> NicknameCheckResponse:
    service = NicknameService()
    return NicknameCheckResponse(available=service.is_available(nickname))
