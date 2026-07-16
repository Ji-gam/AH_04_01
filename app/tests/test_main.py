from unittest.mock import AsyncMock

from app import main
from app.core.config import Env


async def test_lifespan_seeds_health_content_when_env_is_local(monkeypatch):
    """ENV=local이면 셀러리/LLM 키 없이도 서버 기동만으로 개인화 콘텐츠를 볼 수 있어야 한다."""
    seed_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_health_content", seed_mock)
    monkeypatch.setattr(main, "refresh_food_drug_interaction_cache", AsyncMock())
    monkeypatch.setattr(main.config, "ENV", Env.LOCAL)

    async with main.lifespan(main.app):
        pass

    seed_mock.assert_awaited_once()


async def test_lifespan_skips_seeding_when_env_is_not_local(monkeypatch):
    """dev/prod는 실제 생성 파이프라인이 채운 MySQL을 그대로 조회해야 하므로 자동 시드하지 않는다."""
    seed_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_health_content", seed_mock)
    monkeypatch.setattr(main, "refresh_food_drug_interaction_cache", AsyncMock())
    monkeypatch.setattr(main.config, "ENV", Env.PROD)

    async with main.lifespan(main.app):
        pass

    seed_mock.assert_not_awaited()


async def test_lifespan_refreshes_food_drug_interaction_cache_in_every_env(monkeypatch):
    """음식-약물 참조 테이블은 모든 환경에서 동일한 정적 데이터라, ENV와 무관하게 매번
    MySQL에서 읽어 캐싱해야 한다(건강 콘텐츠 픽스처 시딩과 달리 ENV=local 전용이 아님)."""
    refresh_mock = AsyncMock()
    monkeypatch.setattr(main, "seed_health_content", AsyncMock())
    monkeypatch.setattr(main, "refresh_food_drug_interaction_cache", refresh_mock)
    monkeypatch.setattr(main.config, "ENV", Env.PROD)

    async with main.lifespan(main.app):
        pass

    refresh_mock.assert_awaited_once()
