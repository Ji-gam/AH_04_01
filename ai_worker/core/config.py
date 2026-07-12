import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))

    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # RAG 검색 유사도 임계값(Chroma L2 거리, score < threshold만 통과). 임베딩 백엔드가
    # 바뀌면 거리 스케일도 달라지므로 값이 코드에 박히지 않도록 config로 뺀다.
    RAG_SIMILARITY_THRESHOLD: float = 1.4


# 글로벌 싱글톤 인스턴스 생성
settings = Config()
