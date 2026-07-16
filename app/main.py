from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers
from app.core import config
from app.core.config import Env
from app.core.db.databases import AsyncSessionLocal
from app.scripts.seed_health_content import seed_health_content
from app.services.medication_service import refresh_food_drug_interaction_cache

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """`ENV=local`에서는 서버 기동 시 건강 콘텐츠 픽스처를 자동으로 시드한다 — 셀러리/LLM
    키가 없는 팀원도 별도 스크립트 실행 없이 곧장 개인화 콘텐츠를 확인할 수 있게 하기 위함.
    dev/prod는 실제 생성 파이프라인이 채운 MySQL을 그대로 조회하므로 건너뛴다.

    음식-약물 참조 테이블은 모든 환경에서 동일한 정적 데이터라(2026-07-16 SQLite에서 MySQL로
    이전) `seed_food_drug_interaction`으로 미리 시딩된 MySQL 테이블을 앱 기동 시 1회 읽어
    프로세스 메모리에 캐싱한다 — 상세: `app/repositories/food_drug_interaction_repository.py`."""
    if config.ENV == Env.LOCAL:
        await seed_health_content()
    async with AsyncSessionLocal() as session:
        await refresh_food_drug_interaction_cache(session)
    yield


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
    lifespan=lifespan,
)

app.include_router(v1_routers)

if config.ENV == Env.LOCAL:
    from app.admin import register_admin

    register_admin(app)
