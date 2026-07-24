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

    # F-DIET-1/2: 식품영양성분DB API - 별도 서비스 신청이 필요할 수 있어 키를 분리해뒀다.
    # 설정 안 하면 PUBLIC_DATA_API_KEY로 폴백하고, 그것도 없거나 호출이 실패하면
    # app/services/food_nutrition_open_api_client.py가 로컬 시드로 폴백한다.
    FOOD_NUTRITION_API_KEY: str | None = None

    # T-MED-1: CLOVA OCR(네이버 클라우드) - 처방전/약봉투 이미지 인식. 둘 다 설정돼야 실제
    # 호출한다(medication_service._clova_configured). 미설정이면 실제 OCR 없이 인식 실패로
    # 처리되고, dummy_mode 명시 요청 시에만 결정적 더미 결과를 낸다. SECRET_KEY가 "your_"로
    # 시작하면 .env 예시의 미교체 플레이스홀더로 보고 미설정으로 취급한다.
    CLOVA_OCR_SECRET_KEY: str | None = None
    CLOVA_OCR_INVOKE_URL: str | None = None

    # 웹푸시(Web Push) - VAPID 키쌍. 한 번 생성하면 이후 계속 재사용(교체하면 기존 구독이
    # 전부 무효화됨). app/scripts/generate_vapid_keys.py로 1회 생성해서 .env에 넣어둔다.
    VAPID_PUBLIC_KEY: str | None = None
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_CLAIM_EMAIL: str = "mailto:admin@example.com"

    # FCM(Firebase Cloud Messaging) - 웹/네이티브 공통 발송 채널. Firebase 콘솔 > 프로젝트
    # 설정 > 서비스 계정 > "새 비공개 키 생성"으로 받은 json을
    # app/secrets/firebase-service-account.json에 두고 여기 경로를 넣는다(레포 루트 기준
    # 상대경로 - uv run은 항상 레포 루트에서 실행). 설정 안 하면 push_service.py가 FCM
    # 발송만 건너뛰고(웹푸시는 그대로 동작) 조용히 넘어간다.
    FIREBASE_CREDENTIALS_PATH: str | None = None

    # T-LLM-2-async-gateway: ai-worker 서비스 기본 URL (docker-compose 네트워크 내부 호스트명).
    # AIWorkerGateway가 여기에 /retrieve, /generate-structured 경로를 붙여 호출한다.
    AI_WORKER_BASE_URL: str = "http://ai-worker:8001"
    # ai-worker 호출 타임아웃을 용도별로 분리한다. /retrieve는 벡터 검색이라 짧게,
    # /generate-structured는 LLM 생성이라 5초를 흔히 넘기므로 넉넉히 둔다(정상 생성이
    # 타임아웃으로 오인돼 AIWorkerUnavailableError가 나던 문제 방지).
    AI_WORKER_RETRIEVE_TIMEOUT: float = 5.0
    AI_WORKER_GENERATE_TIMEOUT: float = 60.0
    # T-LLM-2-async-gateway: Celery 브로커. docker-compose의 기존 redis 서비스를 재사용한다.
    CELERY_BROKER_URL: str = "redis://redis:6379/0"

    # 소셜 로그인 콜백 처리 후 리다이렉트할 프론트엔드 주소. 로컬 dev 서버(vite) 기준 기본값.
    FRONTEND_URL: str = "http://localhost:5174"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    # 카카오는 비즈앱 전환 전이라 이메일을 거의 못 받는다 (oauth_clients.py의 parse_kakao_userinfo 참고).
    # CLIENT_SECRET은 카카오 콘솔에서 "Client Secret" 보안 기능을 켠 경우에만 필요 - 안 켰으면 빈 값으로 둔다.
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/kakao/callback"
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    NAVER_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/naver/callback"
