import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers
from app.core import config
from app.core.config import Env
from app.core.db.databases import AsyncSessionLocal
from app.repositories.error_log_repository import ErrorLogRepository

from app.scripts.seed_health_content import seed_health_content
from app.scripts.seed_local_super_admin import seed_local_super_admin
from app.services import medication_open_api_client
from app.services.medication_service import refresh_food_drug_interaction_cache
from app.services.push_scheduler import start_push_scheduler

# (2026-07-31) 지금까지 프로젝트 어디에도 logging.basicConfig가 없어서, INFO 레벨
# 로그(로컬 시딩 안내 등)가 전부 조용히 씹히고 있었다 - 파이썬은 설정이 아예 없으면
# WARNING 이상만 최소한으로 찍는 "최후 방어" 핸들러만 동작한다. 앱 전체에 딱 한 번,
# 여기서 기본 설정을 잡아 INFO 레벨 로그도 도커 로그(`docker compose logs fastapi`)에
# 정상적으로 보이게 한다. uvicorn 자체 로거(uvicorn.access 등)는 이미 따로 설정되어
# 있어 영향받지 않는다.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

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
    """음식-약물 참조 테이블은 모든 환경에서 동일한 정적 데이터라(2026-07-16 SQLite에서 MySQL로
    이전) `seed_food_drug_interaction`으로 미리 시딩된 MySQL 테이블을 앱 기동 시 1회 읽어
    프로세스 메모리에 캐싱한다 — 상세: `app/repositories/food_drug_interaction_repository.py`.

    같은 조건(`ENV=local`)에서 슈퍼관리자 계정도 자동 시딩한다 - 관련 환경변수
    (`LOCAL_SUPER_ADMIN_EMAIL`/`_PASSWORD`)가 없으면 아무 일도 안 하므로, 이 값을 안
    채운 팀원에게는 아무 영향이 없다 - 상세: `app/scripts/seed_local_super_admin.py`."""
    if config.ENV == Env.LOCAL:
        await seed_health_content()
        await seed_local_super_admin()

    async with AsyncSessionLocal() as session:
        await refresh_food_drug_interaction_cache(session)
    # (웹푸시, 임시 구현) celery-beat이 아직 없어서 fastapi 프로세스 안에서 APScheduler로
    # 대신 돈다 - 자세한 배경은 app/services/push_scheduler.py의 docstring 참고. app.state에
    # 보관하는 이유: 스누즈(push_routers.py)가 이 스케줄러에 일회성 지연 발송 job을 추가해야 한다.
    app.state.push_scheduler = start_push_scheduler()
    yield
    app.state.push_scheduler.shutdown()
    await medication_open_api_client.close_http_client()


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


async def _log_unhandled_exception(request: Request, exc: Exception) -> ORJSONResponse:
    """(2026-07-28) 챗봇 오류는 이미 파일 로그로 개인정보 제거해서 남기고 있었는데,
    나머지 API는 안 잡힌 예외가 나도 도커 로그에만 흘러가고 DB에 남거나 관리자 화면에서
    조회할 방법이 없었다 - 이 핸들러 + error_logs 테이블로 그 공백을 메운다. 같은 이유로
    전체 트레이스백/요청 바디는 안 남기고 예외 타입 + 잘라낸 메시지 + 경로만 남긴다.
    로깅 자체가 실패해도(DB 문제 등) 원래 500 응답은 그대로 내려가야 한다."""
    try:
        async with AsyncSessionLocal() as session:
            await ErrorLogRepository().log(
                session,
                method=request.method,
                path=request.url.path,
                exception_type=type(exc).__name__,
                message=str(exc),
                status_code=500,
            )
    except Exception:
        pass
    return ORJSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다."})


app.add_exception_handler(Exception, _log_unhandled_exception)

if config.ENV == Env.LOCAL:
    from app.admin import register_admin

    register_admin(app)

    # [임시, 로컬 전용] error_logs 파이프라인 자체가 제대로 동작하는지 확인하기 위한
    # 테스트용 엔드포인트 - 일부러 예외를 던진다. 확인 끝나면 이 블록 통째로 지우면 됨.
    @app.get("/api/v1/_debug/trigger-error")
    async def _debug_trigger_error() -> None:
        raise RuntimeError("버그 리포트 파이프라인 테스트용 - 실제 버그 아님")
