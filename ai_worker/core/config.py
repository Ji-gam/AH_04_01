import zoneinfo
from dataclasses import field

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))

    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    # 분류·구조화 추출·논문 답변은 결정적이어야 하므로 기본 0. 창의성이 필요한
    # 용도가 생기면 호출부에서 개별적으로 올린다(기본값은 결정성 우선).
    OPENAI_TEMPERATURE: float = 0.0


# 글로벌 싱글톤 인스턴스 생성
settings = Config()
