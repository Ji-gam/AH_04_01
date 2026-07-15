from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import cast

from app.repositories.content_repository import ContentRepository
from app.services.content_service import ContentService, _today_kst
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
    """이 fake는 LLM/retriever를 전혀 참조하지 않는다 — ContentService의 조회 경로가
    LLM에 의존하지 않는다는 걸 테스트로 강제하기 위함(라이브 생성 제거, 2026-07-08 확정)."""

    def __init__(self) -> None:
        self.items: list[FakeHealthContent] = []
        self.save_calls = 0
        self._next_id = 1

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

    async def list_by_diseases(
        self, session, disease_codes: list[str] | None, category: str | None, limit: int | None = None
    ) -> list[FakeHealthContent]:
        results = [
            item
            for item in self.items
            if (disease_codes is None or item.disease_code in disease_codes)
            and (category is None or item.category == category)
        ]
        results = sorted(results, key=lambda item: item.content_date, reverse=True)
        return results[:limit] if limit is not None else results

    async def get_by_id(self, session, content_id: int) -> FakeHealthContent | None:
        return next((item for item in self.items if item.id == content_id), None)

    async def list_related(
        self, session, disease_code: str, exclude_category: str, exclude_id: int, limit: int = 5
    ) -> list[FakeHealthContent]:
        results = [
            item
            for item in self.items
            if item.disease_code == disease_code and item.category != exclude_category and item.id != exclude_id
        ]
        results = sorted(results, key=lambda item: item.content_date, reverse=True)
        return results[:limit]

    def seed(self, disease_code: str, category: str, content_date: date, title: str = "캐시된 제목") -> int:
        content_id = self._next_id
        self.items.append(
            FakeHealthContent(
                id=content_id,
                disease_code=disease_code,
                category=category,
                content_date=content_date,
                title=title,
                summary="요약",
                body="본문",
            )
        )
        self._next_id += 1
        return content_id


def _build_service(repository: FakeContentRepository) -> ContentService:
    return ContentService(repository=cast(ContentRepository, repository))


async def test_disease_filter_returns_only_matching_diseases():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("당뇨", "FOOD", today)
    repository.seed("고혈압", "LIFESTYLE", today)
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=["당뇨"])

    assert len(items) == 2
    assert {item["disease_code"] for item in items} == {"당뇨"}


async def test_missing_combo_is_silently_skipped_not_generated():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=["당뇨"])

    assert len(items) == 1
    assert items[0]["category"] == "LIFESTYLE"
    assert repository.save_calls == 0


async def test_diseases_none_returns_all_cached_content():
    """diseases=None이면 질환과 무관하게 전체를 반환한다(비로그인/개인화 판단은 호출자 몫)."""
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("고혈압", "FOOD", today)
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=None)

    assert {item["disease_code"] for item in items} == {"당뇨", "고혈압"}


async def test_category_filter_applies_regardless_of_disease_filter():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "LIFESTYLE", today)
    repository.seed("당뇨", "FOOD", today)
    repository.seed("고혈압", "FOOD", today)
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=None, category="FOOD")

    assert {item["disease_code"] for item in items} == {"당뇨", "고혈압"}
    assert all(item["category"] == "FOOD" for item in items)


async def test_limit_caps_number_of_items_returned():
    repository = FakeContentRepository()
    today = _today_kst()
    yesterday = today - timedelta(days=1)
    repository.seed("당뇨", "LIFESTYLE", today, title="오늘 카드")
    repository.seed("당뇨", "FOOD", yesterday, title="어제 카드")
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=None, limit=1)

    assert len(items) == 1
    assert items[0]["title"] == "오늘 카드"


async def test_feed_accumulates_across_dates_newest_first():
    repository = FakeContentRepository()
    today = _today_kst()
    yesterday = today - timedelta(days=1)
    repository.seed("당뇨", "LIFESTYLE", yesterday, title="어제 카드")
    repository.seed("당뇨", "LIFESTYLE", today, title="오늘 카드")
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=["당뇨"])

    assert [item["title"] for item in items] == ["오늘 카드", "어제 카드"]


async def test_response_includes_disclaimer_from_safety_service():
    repository = FakeContentRepository()
    today = _today_kst()
    repository.seed("당뇨", "FOOD", today)
    service = _build_service(repository)

    items = await service.get_contents(session=None, diseases=["당뇨"], category="FOOD")

    assert items[0]["disclaimer"] == DISCLAIMER_TEXT


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


async def test_seed_from_fixture_honors_explicit_content_date_for_same_day_variety():
    """소주제별로 backdate된 `content_date`가 있으면, 같은 (질환, 카테고리)라도 날짜가
    다르면 유니크 제약에 걸리지 않고 셋 다 삽입돼야 한다(장르당 3장 요구사항)."""
    repository = FakeContentRepository()
    today = _today_kst()
    service = ContentService(repository=cast(ContentRepository, repository))
    entries = [
        {
            "disease_code": "당뇨",
            "category": "LIFESTYLE",
            "title": f"t{i}",
            "summary": "s",
            "body": "b",
            "image_prompt": None,
            "content_date": (today - timedelta(days=i)).isoformat(),
        }
        for i in range(3)
    ]

    inserted = await service.seed_from_fixture(session=None, entries=entries)

    assert inserted == 3
    assert repository.save_calls == 3
    assert {item.content_date for item in repository.items} == {today - timedelta(days=i) for i in range(3)}


async def test_seed_from_fixture_without_content_date_defaults_to_today():
    repository = FakeContentRepository()
    today = _today_kst()
    service = ContentService(repository=cast(ContentRepository, repository))
    entries = [
        {"disease_code": "당뇨", "category": "FOOD", "title": "t", "summary": "s", "body": "b", "image_prompt": None},
    ]

    await service.seed_from_fixture(session=None, entries=entries)

    assert repository.items[0].content_date == today


async def test_get_content_by_id_returns_matching_item():
    repository = FakeContentRepository()
    today = _today_kst()
    content_id = repository.seed("당뇨", "LIFESTYLE", today, title="상세용 카드")
    service = _build_service(repository)

    item = await service.get_content_by_id(session=None, content_id=content_id)

    assert item is not None
    assert item["title"] == "상세용 카드"


async def test_get_content_by_id_returns_none_when_missing():
    repository = FakeContentRepository()
    service = _build_service(repository)

    item = await service.get_content_by_id(session=None, content_id=999)

    assert item is None


async def test_get_related_contents_excludes_same_category_and_self():
    repository = FakeContentRepository()
    today = _today_kst()
    base_id = repository.seed("당뇨", "LIFESTYLE", today, title="기준 카드")
    repository.seed("당뇨", "LIFESTYLE", today, title="같은 카테고리라 제외")
    food_id = repository.seed("당뇨", "FOOD", today, title="관련 카드")
    repository.seed("암", "FOOD", today, title="다른 질환이라 제외")
    service = _build_service(repository)

    items = await service.get_related_contents(
        session=None, disease_code="당뇨", exclude_category="LIFESTYLE", exclude_id=base_id
    )

    assert [item["id"] for item in items] == [food_id]


async def test_get_related_contents_respects_limit():
    repository = FakeContentRepository()
    today = _today_kst()
    for i in range(6):
        repository.seed("당뇨", "FOOD", today - timedelta(days=i), title=f"관련 카드 {i}")
    service = _build_service(repository)

    items = await service.get_related_contents(
        session=None, disease_code="당뇨", exclude_category="LIFESTYLE", exclude_id=-1, limit=5
    )

    assert len(items) == 5
