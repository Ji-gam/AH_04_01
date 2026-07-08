from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.apis.v1 import v1_routers
from app.core import config
from app.core.rate_limit import limiter

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

# [소셜로그인 추가에 따른 필수 조건] CORS 설정이 없으면 프론트(예: 127.0.0.1:5173)와
# 백엔드(127.0.0.1:8000) 간 쿠키(refresh_token) 인증 요청이 브라우저에서 차단된다.
# allow_origins는 "*"(전체허용)이 아니라 정확한 주소를 명시해야 쿠키(withCredentials)가 통과된다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_routers)

# [T-AUTH-6] Rate Limiting — signup/login 라우터에 걸어둔 @limiter.limit이 실제로
# 동작하려면 app에 등록해야 한다.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)