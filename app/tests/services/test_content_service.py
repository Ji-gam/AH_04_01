from dataclasses import dataclass, field
from datetime import date
from typing import cast

from app.repositories.content_repository import ContentRepository
from app.services.content_service import CATEGORIES, ContentService, _today_kst
from app.services.safety_service import DISCLAIMER_TEXT
from app.services.user_health_context_service import UserHealthContextService


@dataclass
class FakeHealthContent:
    disease_code: str
    category: str
    content_date: date
    title: str
    summary: str
    body: str
    image_prompt: str | None = None
    source_refs: list[str] = field(default_factory=list)


class FakeContentRepository:
    """이 fake는 LLM/retriever를 전혀 참조하지 않는다 — ContentService의 조회 경로가
    LLM에 의존하지 않는다는 걸 테스트로 강제하기 위함(라이브 생성 제거, 2026-07-08 확정)."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str, date], FakeHealthContent] = {}
        self.save_calls = 0

    async def get_by_disease_category_date(
        self, session, disease_code: str, category: str, content_date: date
    ) -> FakeHealthContent | None:
        return self.store.get((disease_code, category, content_date))

    async def save(self, session, **fields) -> FakeHealthContent:
        self.save_calls += 1
        content = FakeHealthContent(**fields)
        self.store[(content.disease_code, content.category, content.content_date)] = content
        return content

    def seed(self, disease_code: str, category: str, content_date: date, title: str = "캐시된 제목") -> None:
        self.store[(disease_code, category, content_date)] = FakeHealthContent(
            disease_code=disease_code,
            category=category,
            content_date=content_date,
            title=title,
            summary="요약",
            body="본문",
        )


class FakeHealthContextService:
    def __init__(self, conditions: list[str]) -> None:
        self._conditions = conditions

    def get_context(self, profile_id: int) -> dict:
        return {"profile_id": profile_id, "conditions": self._conditions, "family_history": [], "medications": []}


def _build_service(repository: FakeContentRepository, conditions: list[str]) -> ContentService:
    return ContentService(
        repository=cast(ContentRepository, repository),
        health_context_service=cast(UserHealthContextService, FakeHealthContextService(conditions)),
    )


async def test_returns_only_cached_items_for_users_conditions():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("당뇨", "FOOD", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents_for_profile(session=None, profile_id=1)

    assert len(results) == 2
    assert {r["category"] for r in results} == {"LIFESTYLE", "FOOD"}


async def test_missing_combo_is_silently_skipped_not_generated():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents_for_profile(session=None, profile_id=1)

    assert len(results) == 1
    assert results[0]["category"] == "LIFESTYLE"
    assert repository.save_calls == 0


async def test_no_conditions_returns_empty_list():
    repository = FakeContentRepository()
    service = _build_service(repository, [])

    results = await service.get_contents_for_profile(session=None, profile_id=1)

    assert results == []


async def test_category_filter_returns_only_that_category():
    repository = FakeContentRepository()
    today = _today_kst()
    for category in CATEGORIES:
        repository.seed("당뇨", category, today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents_for_profile(session=None, profile_id=1, category="FOOD")

    assert len(results) == 1
    assert results[0]["category"] == "FOOD"


async def test_multiple_conditions_each_return_own_cached_card():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("고혈압", "LIFESTYLE", today)
    service = _build_service(repository, ["당뇨", "고혈압"])

    results = await service.get_contents_for_profile(session=None, profile_id=1, category="LIFESTYLE")

    assert {r["disease_code"] for r in results} == {"당뇨", "고혈압"}


async def test_response_includes_disclaimer_from_safety_service():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "FOOD", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents_for_profile(session=None, profile_id=1, category="FOOD")

    assert results[0]["disclaimer"] == DISCLAIMER_TEXT


async def test_seed_from_fixture_inserts_new_entries():
    repository = FakeContentRepository()
    service = ContentService(repository=cast(ContentRepository, repository))
    entries = [
        {
            "disease_code": "암",
            "category": "LIFESTYLE",
            "title": "t",
            "summary": "s",
            "body": "b",
            "image_prompt": None,
        },
        {"disease_code": "암", "category": "FOOD", "title": "t2", "summary": "s2", "body": "b2", "image_prompt": None},
    ]

    inserted = await service.seed_from_fixture(session=None, entries=entries)

    assert inserted == 2
    assert repository.save_calls == 2


async def test_seed_from_fixture_skips_already_cached_combo():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("암", "LIFESTYLE", today)
    service = ContentService(repository=cast(ContentRepository, repository))
    entries = [
        {
            "disease_code": "암",
            "category": "LIFESTYLE",
            "title": "t",
            "summary": "s",
            "body": "b",
            "image_prompt": None,
        },
    ]

    inserted = await service.seed_from_fixture(session=None, entries=entries)

    assert inserted == 0
    assert repository.save_calls == 0
