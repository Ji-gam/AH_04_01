import os
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    ENV: Env = Env.LOCAL
    SECRET_KEY: str = f"default-secret-key{uuid.uuid4().hex}"
    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    TEMPLATE_DIR: str = os.path.join(Path(__file__).resolve().parent.parent, "templates")

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "pw1234"
    DB_NAME: str = "ai_health"
    DB_CONNECT_TIMEOUT: int = 5
    DB_CONNECTION_POOL_MAXSIZE: int = 10

    COOKIE_DOMAIN: str = "localhost"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 14 * 24 * 60
    JWT_LEEWAY: int = 5

    # T-LLM-2: 설정 안 하면 app/services/llm_stub.py가 고정 문자열 stub으로 폴백한다.
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # T-MED-4: 공공데이터포털(data.go.kr) 서비스키. 의약품 낱알식별 API와 의약품제품
    # 허가정보 API가 같은 계정의 서비스키를 공유한다. 설정 안 하면
    # app/services/medication_open_api_client.py가 빈 리스트를 반환한다.
    PUBLIC_DATA_API_KEY: str | None = None

    # T-LLM-2-async-gateway: ai-worker 서비스 기본 URL (docker-compose 네트워크 내부 호스트명).
    # AIWorkerGateway가 여기에 /retrieve, /generate-structured 경로를 붙여 호출한다.
    AI_WORKER_BASE_URL: str = "http://ai-worker:8001"

    # T-LLM-2-async-gateway: Celery 브로커. docker-compose의 기존 redis 서비스를 재사용한다.
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
