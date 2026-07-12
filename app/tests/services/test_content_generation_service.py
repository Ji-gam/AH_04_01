"""
T-LLM-3-manual-content-generation: QA 전용 수동 콘텐츠 생성 트리거.

`ContentService`(순수 캐시 조회, LLM 미호출)와 달리, 이 서비스는 실제로 LLM 생성을
요청한다 — #83(게이트웨이 생성 타임아웃 분리) 수정을 프론트에서 수동으로 검증하기
위한 QA 전용 경로이지, 프로덕션 사용자 플로우가 아니다.
"""

from dataclasses import dataclass, field
from datetime import date

import pytest

from app.services import content_generation_service as content_generation_service_module
from app.services.ai_worker_gateway import (
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.content_generation_service import ContentGenerationService
from app.services.content_service import CATEGORIES, CATEGORY_TOPICS, POPULAR_DISEASES, _today_kst
from app.services.safety_service import DISCLAIMER_TEXT


@dataclass
class FakeHealthContent:
    id: int
    disease_code: str
    category: str
    content_date: date
    title: str
    summary: str
    body: str
    image_prompt: str | None = None
    source_refs: list[str] = field(default_factory=list)


class FakeContentRepository:
    def __init__(self) -> None:
        self.items: list[FakeHealthContent] = []
        self._next_id = 1
        self.save_calls = 0

    async def get_by_disease_category_date(
        self, session, disease_code: str, category: str, content_date: date
    ) -> FakeHealthContent | None:
        for item in self.items:
            if (item.disease_code, item.category, item.content_date) == (disease_code, category, content_date):
                return item
        return None

    async def save(self, session, **fields) -> FakeHealthContent:
        self.save_calls += 1
        content = FakeHealthContent(id=self._next_id, **fields)
        self._next_id += 1
        self.items.append(content)
        return content

    async def update_card(
        self, session, content: FakeHealthContent, *, title: str, summary: str, body: str, image_prompt: str | None
    ) -> FakeHealthContent:
        content.title = title
        content.summary = summary
        content.body = body
        content.image_prompt = image_prompt
        return content


async def fake_generate_content_card(disease_code: str, category: str, topic: str) -> dict:
    return {"title": f"{disease_code}-{category}-{topic}", "summary": "요약", "body": "본문", "image_prompt": None}


def _failing_generator(exc: Exception):
    async def _raise(disease_code: str, category: str, topic: str) -> dict:
        raise exc

    return _raise


async def test_generate_and_save_creates_new_content_when_no_cache_exists(monkeypatch):
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", fake_generate_content_card)
    repository = FakeContentRepository()
    service = ContentGenerationService(repository=repository)

    result = await service.generate_and_save(session=None, disease_code="당뇨", category="LIFESTYLE", topic="운동")

    assert result["disease_code"] == "당뇨"
    assert result["category"] == "LIFESTYLE"
    assert result["title"] == "당뇨-LIFESTYLE-운동"
    assert result["disclaimer"] == DISCLAIMER_TEXT
    assert "id" in result
    assert repository.save_calls == 1


async def test_generate_and_save_updates_existing_cache_instead_of_raising_unique_violation(monkeypatch):
    """같은 (질환, 카테고리, 오늘) 캐시가 이미 있으면 새로 만들지 않고 갱신한다(버튼 반복 클릭 대비)."""
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", fake_generate_content_card)
    repository = FakeContentRepository()
    today = _today_kst()
    repository.items.append(
        FakeHealthContent(
            id=99, disease_code="당뇨", category="LIFESTYLE", content_date=today, title="기존", summary="s", body="b"
        )
    )
    service = ContentGenerationService(repository=repository)

    result = await service.generate_and_save(session=None, disease_code="당뇨", category="LIFESTYLE", topic="운동")

    assert result["id"] == 99
    assert result["title"] == "당뇨-LIFESTYLE-운동"
    assert repository.save_calls == 0
    assert len(repository.items) == 1


async def test_generate_and_save_picks_random_combo_when_unspecified(monkeypatch):
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", fake_generate_content_card)
    repository = FakeContentRepository()
    service = ContentGenerationService(repository=repository)

    result = await service.generate_and_save(session=None)

    assert result["disease_code"] in POPULAR_DISEASES
    assert result["category"] in CATEGORIES
    assert any(
        result["category"] == c and result["title"].endswith(topic)
        for c, topics in [(result["category"], CATEGORY_TOPICS[result["category"]])]
        for topic in topics
    )


@pytest.mark.parametrize(
    "exc",
    [
        AIWorkerUnavailableError("ai_worker 응답 없음"),
        AIWorkerInvalidRequestError("잘못된 요청"),
        AIWorkerProcessingError("형식 이상"),
    ],
)
async def test_generate_and_save_propagates_gateway_errors_without_swallowing(monkeypatch, exc):
    """ContentService의 retrieve 경로(_search_chunks)와 달리, 생성 실패는 조용히 삼키지 않고
    호출자(라우터)가 처리하도록 그대로 전파한다."""
    monkeypatch.setattr(content_generation_service_module, "generate_content_card", _failing_generator(exc))
    service = ContentGenerationService(repository=FakeContentRepository())

    with pytest.raises(type(exc)):
        await service.generate_and_save(session=None, disease_code="당뇨", category="LIFESTYLE", topic="운동")
