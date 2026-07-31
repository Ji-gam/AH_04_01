from unittest.mock import AsyncMock

from app import main
from app.core.config import Env


async def test_lifespan_refreshes_food_drug_interaction_cache_in_every_env(monkeypatch):
    """음식-약물 참조 테이블은 모든 환경에서 동일한 정적 데이터라, ENV와 무관하게 매번
    MySQL에서 읽어 캐싱해야 한다.

    (2026-07-30, T-LLM-6) 예전엔 `ENV=local`에서 건강 콘텐츠 픽스처를 자동 시드하는 분기가
    같이 있었고 그 동작을 검증하는 테스트가 둘 더 있었다. T-LLM-3이 실제 뉴스 수집으로
    대체되면서 시드할 픽스처 자체가 없어졌으므로(수집은 관리자 버튼/스크립트로 트리거) 함께 지웠다."""
    refresh_mock = AsyncMock()
    monkeypatch.setattr(main, "refresh_food_drug_interaction_cache", refresh_mock)
    monkeypatch.setattr(main.config, "ENV", Env.PROD)

    async with main.lifespan(main.app):
        pass

    refresh_mock.assert_awaited_once()
