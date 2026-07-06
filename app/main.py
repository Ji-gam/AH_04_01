from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.apis.v1 import v1_routers
from app.apis.v1.auth_routers import limiter as auth_limiter
from app.core import config
from app.core.db.databases import initialize_tortoise

app = FastAPI(
    default_response_class=ORJSONResponse, docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json"
)
initialize_tortoise(app)

# [핀포인트 추가 - CORS 누락 수정]
# 프론트(예: localhost:5173)와 백엔드(127.0.0.1:8000)가 서로 다른 주소(origin)라서,
# 이게 없으면 브라우저가 쿠키(refresh_token)를 실어서 보내는 요청 자체를 차단합니다.
# allow_origins는 "*"(전체허용)이 아니라 정확한 주소를 명시해야 쿠키(withCredentials)가 통과됩니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [핀포인트 추가] auth_routers.py의 signup/login에 걸어둔 @limiter.limit이 실제로 동작하려면 앱에 등록해야 합니다.
app.state.limiter = auth_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]  # slowapi/mypy 알려진 시그니처 불일치
app.add_middleware(SlowAPIMiddleware)

app.include_router(v1_routers)
