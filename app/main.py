from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "회원가입/로그인/토큰 재발급. Access Token은 응답 body로, Refresh Token은 httpOnly 쿠키로 내려간다.",
    },
    {
        "name": "users",
        "description": "로그인한 계정(User)의 정보 조회/수정. 개인정보(이름/성별/생일/휴대폰번호)는 Profile 기준으로 응답한다.",
    },
    {
        "name": "notifications",
        "description": "복약 알림 일정(Notification Schedule) CRUD. profile_id 기준으로 스코핑한다.",
    },
]

app = FastAPI(
    title="AI HealthCare API",
    summary="복약·건강관리 서비스(ReMedi) 백엔드 API",
    description=(
        "레이어 우선 구조(Router → Service → Repository)의 FastAPI 백엔드입니다. "
        "요구사항 원본은 `docs/PRD_ReMedi_v1.1.md`/`docs/TRD_ReMedi_v1.1.md`, "
        "구조/규칙은 `docs/CODING_RULES_v1.0.md`를 참고하세요."
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    default_response_class=ORJSONResponse,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(v1_routers)
