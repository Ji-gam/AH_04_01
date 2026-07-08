from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import cast

from app.repositories.content_repository import ContentRepository
from app.services.content_service import ContentService, _today_kst
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
        self.items: list[FakeHealthContent] = []
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
        content = FakeHealthContent(**fields)
        self.items.append(content)
        return content

    async def list_by_diseases(
        self, session, disease_codes: list[str] | None, category: str | None
    ) -> list[FakeHealthContent]:
        results = [
            item
            for item in self.items
            if (disease_codes is None or item.disease_code in disease_codes)
            and (category is None or item.category == category)
        ]
        return sorted(results, key=lambda item: item.content_date, reverse=True)

    def seed(self, disease_code: str, category: str, content_date: date, title: str = "캐시된 제목") -> None:
        self.items.append(
            FakeHealthContent(
                disease_code=disease_code,
                category=category,
                content_date=content_date,
                title=title,
                summary="요약",
                body="본문",
            )
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


async def test_personalized_profile_returns_only_own_conditions():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("당뇨", "FOOD", today)
    repository.seed("고혈압", "LIFESTYLE", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents(session=None, profile_id=1)

    assert len(results) == 2
    assert {r["disease_code"] for r in results} == {"당뇨"}


async def test_missing_combo_is_silently_skipped_not_generated():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents(session=None, profile_id=1)

    assert len(results) == 1
    assert results[0]["category"] == "LIFESTYLE"
    assert repository.save_calls == 0


async def test_anonymous_request_returns_all_cached_content():
    """profile_id=None(비로그인)이면 등록된 질환과 무관하게 전체를 반환한다."""
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("고혈압", "FOOD", today)
    service = _build_service(repository, conditions=["당뇨"])  # 어차피 profile_id=None이라 무시됨

    results = await service.get_contents(session=None, profile_id=None)

    assert {r["disease_code"] for r in results} == {"당뇨", "고혈압"}


async def test_profile_without_registered_conditions_returns_all_cached_content():
    """질환 미등록 프로필은 비로그인과 동일하게 전체 콘텐츠를 본다."""
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("고혈압", "FOOD", today)
    service = _build_service(repository, conditions=[])

    results = await service.get_contents(session=None, profile_id=1)

    assert {r["disease_code"] for r in results} == {"당뇨", "고혈압"}


async def test_category_filter_applies_regardless_of_personalization():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("당뇨", "FOOD", today)
    repository.seed("고혈압", "FOOD", today)
    service = _build_service(repository, conditions=[])

    results = await service.get_contents(session=None, profile_id=None, category="FOOD")

    assert {r["disease_code"] for r in results} == {"당뇨", "고혈압"}
    assert all(r["category"] == "FOOD" for r in results)


async def test_feed_accumulates_across_dates_newest_first():
    repository = FakeContentRepository()
    today = _today_kst()
    yesterday = today - timedelta(days=1)
    repository.seed("당뇨", "LIFESTYLE", yesterday, title="어제 카드")
    repository.seed("당뇨", "LIFESTYLE", today, title="오늘 카드")
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents(session=None, profile_id=1)

    assert [r["title"] for r in results] == ["오늘 카드", "어제 카드"]


async def test_response_includes_disclaimer_from_safety_service():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "FOOD", today)
    service = _build_service(repository, ["당뇨"])

    results = await service.get_contents(session=None, profile_id=1, category="FOOD")

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
