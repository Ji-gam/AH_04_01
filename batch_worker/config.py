import os
from pydantic_settings import BaseSettings

class BatchSettings(BaseSettings):
    DATA_GV_KR: str = os.getenv("DATA_GV_KR", "1809a405b56fdd59e50935e26276b7f69e2ff06d8d72bce997b72e94b0b393a4")
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")

settings = BatchSettings()
os.makedirs(settings.DATA_DIR, exist_ok=True)
