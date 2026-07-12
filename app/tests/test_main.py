from unittest.mock import AsyncMock

from app import main
from app.core.config import Env


async def test_lifespan_seeds_health_content_when_env_is_local(monkeypatch):
    """ENV=local이면 셀러리/LLM 키 없이도 서버 기동만으로 개인화 콘텐츠를 볼 수 있어야 한다."""
    seed_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_health_content", seed_mock)
    monkeypatch.setattr(main.config, "ENV", Env.LOCAL)

    async with main.lifespan(main.app):
        pass

    seed_mock.assert_awaited_once()


async def test_lifespan_skips_seeding_when_env_is_not_local(monkeypatch):
    """dev/prod는 실제 생성 파이프라인이 채운 MySQL을 그대로 조회해야 하므로 자동 시드하지 않는다."""
    seed_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_health_content", seed_mock)
    monkeypatch.setattr(main.config, "ENV", Env.PROD)

    async with main.lifespan(main.app):
        pass

    seed_mock.assert_not_awaited()
