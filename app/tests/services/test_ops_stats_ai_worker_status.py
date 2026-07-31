"""AI-worker 상태 표시의 회귀 방지 테스트.

예전 구현은 ai_worker **루트 경로**에 GET해서 응답이 오기만 하면(404여도) "정상"으로 봤다.
ai_worker는 루트에 라우트가 없어 항상 404를 주므로, 사실상 "TCP가 열려 있다"만 확인하는
셈이었다. 그래서 카드요약이 전부 실패하는 상황에서도 관리자 대시보드가 "정상"이라 표시해
원인 파악을 오히려 방해했다(2026-07-31).
"""

import httpx

from app.core import config
from app.repositories.ops_stats_repository import OpsStatsRepository


async def test_ai_worker_status_checks_the_health_endpoint(monkeypatch) -> None:  # noqa: ANN001
    """루트가 아니라 `/health`를 봐야 한다 - 루트는 라우트가 없어 늘 404다."""
    requested: list[str] = []

    async def _fake_get(self, url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        requested.append(url)
        return httpx.Response(200, json={"status": "healthy", "db_loaded": True})

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    assert await OpsStatsRepository().ai_worker_status() == "ok"
    assert requested == [f"{config.AI_WORKER_BASE_URL}/health"]


async def test_ai_worker_status_reports_down_on_error_response(monkeypatch) -> None:  # noqa: ANN001
    """응답이 왔어도 2xx가 아니면 "다운"이다. 이게 예전 구현이 놓친 지점이다."""

    async def _fake_get(self, url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    assert await OpsStatsRepository().ai_worker_status() == "down"


async def test_ai_worker_status_reports_down_when_unreachable(monkeypatch) -> None:  # noqa: ANN001
    """연결 자체가 안 되면 "다운"(기존 동작 유지)."""

    async def _fake_get(self, url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        raise httpx.ConnectError("연결 실패")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    assert await OpsStatsRepository().ai_worker_status() == "down"
