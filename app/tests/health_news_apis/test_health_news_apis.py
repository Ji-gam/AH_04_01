"""T-LLM-6 건강 뉴스 API 테스트.

관리자 엔드포인트는 `get_current_admin_user` 의존성을 덮어쓰지 않고, 실제로 가입 → is_admin
승격 → 로그인해서 진짜 토큰으로 호출한다 - 권한 가드 자체가 동작하는지도 같이 확인하려고.

수집/카드요약은 네트워크와 LLM을 타므로 monkeypatch로 갈아끼운다(conftest가 테스트 중 실제
외부 키 사용을 막고 있고, 실제 호출은 비결정적이라 테스트에 넣을 수 없다). 실제 RSS·OpenAI로
동작하는지는 별도로 로컬에서 확인했다.
"""

from datetime import datetime, timedelta

import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from starlette import status

from app.dtos.health_news_dto import CardSlide, CardSummary
from app.main import app
from app.models.health_news import HealthNews
from app.models.users import User
from app.repositories.health_news_repository import HealthNewsRepository
from app.services import health_news_card_summary as card_summary_module
from app.services import health_news_service as health_news_service_module
from app.services import health_news_source as health_news_source_module
from app.services.ai_worker_gateway import AIWorkerUnavailableError
from app.services.health_news_source import KORMEDI, FetchResult, ParsedArticle
from app.tests.conftest import TestSessionLocal

_BASE = "http://test"


def _only_one_source(monkeypatch) -> None:  # noqa: ANN001
    """수집 테스트를 매체 하나로 고정한다.

    실제 `ALL_SOURCES`에는 매체가 여럿 있어서, 그대로 두면 가짜 `fetch`가 매체 수만큼 불려
    기대값이 매체를 추가할 때마다 어긋난다. 여러 매체를 합산하는 동작은 아래
    `test_collect_adds_up_every_source` / `test_collect_keeps_going_when_one_source_fails`가
    따로 검증한다."""
    monkeypatch.setattr(health_news_source_module, "ALL_SOURCES", (KORMEDI,))


async def _signup_login_admin(client: AsyncClient, email: str = "newsadmin@example.com") -> str:
    """가입한 뒤 DB에서 is_admin을 올리고 다시 로그인해 관리자 토큰을 받는다."""
    phone_number = "010" + str(abs(hash(email)))[:8]
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "Password123!",
            "name": "뉴스관리자",
            "gender": "FEMALE",
            "birth_date": "1990-01-01",
            "phone_number": phone_number,
        },
    )
    async with TestSessionLocal() as session:
        await session.execute(update(User).where(User.email == email).values(is_admin=True))
        await session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    return login.json()["access_token"]


def _card_summary(tag: str = "수면") -> dict:
    return CardSummary(
        slides=[
            CardSlide(icon_key="moon", tag=tag, stat="7시간", text="잠이 부족하면 혈당이 흔들립니다."),
            CardSlide(icon_key="dumbbell", tag="운동", stat="주 150분", text="중강도 운동을 나눠서 채워도 됩니다."),
            CardSlide(icon_key="apple", tag="식단", stat="-4mmHg", text="채소를 먼저 먹으면 혈당이 천천히 오릅니다."),
        ]
    ).model_dump()


async def _seed_news(
    *,
    title: str = "테스트 건강 기사",
    source_url: str = "https://kormedi.com/1/",
    published_at: datetime | None = None,
    with_summary: bool = True,
) -> int:
    async with TestSessionLocal() as session:
        news = await HealthNewsRepository().save(
            session,
            source="KORMEDI",
            source_name="코메디닷컴",
            source_url=source_url,
            title=title,
            published_at=published_at or datetime(2026, 7, 30, 9, 0, 0),
            body_text="첫 단락입니다.\n\n두 번째 단락입니다.",
            image_url="https://cdn.kormedi.com/photo.jpg",
            image_caption="사진=게티이미지뱅크",
            source_categories=["건강", "당뇨"],
            card_summary=_card_summary() if with_summary else None,
        )
        return news.id


# ── 공개 피드 ────────────────────────────────────────────────────────────────


async def test_feed_is_public_and_returns_items() -> None:
    """건강정보 화면은 로그인 없이도 볼 수 있어야 한다(기존 '정보' 탭과 같은 정책)."""
    await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news")

    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["source_name"] == "코메디닷컴"
    assert items[0]["has_card_summary"] is True


async def test_feed_omits_body_text_to_keep_the_list_light() -> None:
    """본문은 기사마다 1~3KB씩이라 목록에 담으면 첫 화면만 무거워진다."""
    await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news")

    assert "body_text" not in response.json()["items"][0]


async def test_feed_is_sorted_by_published_at_desc() -> None:
    """정렬 기준은 수집 시각이 아니라 발행일이다 - 수집이 밀려도 순서가 뒤집히지 않아야 한다."""
    base = datetime(2026, 7, 30, 9, 0, 0)
    old_id = await _seed_news(source_url="https://kormedi.com/old/", published_at=base - timedelta(days=2))
    new_id = await _seed_news(source_url="https://kormedi.com/new/", published_at=base)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news")

    assert [item["id"] for item in response.json()["items"]] == [new_id, old_id]


async def test_feed_shows_articles_without_summary_but_flags_them() -> None:
    """요약이 없어도 원문은 읽을 수 있으므로 피드에서 감추지 않는다 - 버튼만 비활성으로 두면 된다."""
    await _seed_news(with_summary=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news")

    assert response.json()["items"][0]["has_card_summary"] is False


async def test_feed_respects_limit() -> None:
    for i in range(3):
        await _seed_news(source_url=f"https://kormedi.com/{i}/")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news?limit=2")

    assert len(response.json()["items"]) == 2


# ── 상세 ─────────────────────────────────────────────────────────────────────


async def test_detail_includes_card_summary_so_no_extra_request_is_needed() -> None:
    """[카드요약보기]를 눌렀을 때 대기가 없어야 한다(TRD "별도 대기 없이") - 그래서 상세 응답에
    카드요약이 함께 실려 온다."""
    news_id = await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get(f"/api/v1/news/{news_id}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body["card_summary"]["slides"]) == 3
    assert body["card_summary"]["slides"][0]["icon_key"] == "moon"
    assert body["body_text"].count("\n\n") == 1
    assert body["image_caption"] == "사진=게티이미지뱅크"


async def test_detail_always_attaches_disclaimer() -> None:
    """REQ-INFO-004. DB에 저장하지 않고 응답 시점에 붙이므로, 문구가 바뀌면 기존 기사도 함께 바뀐다."""
    news_id = await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get(f"/api/v1/news/{news_id}")

    assert response.json()["disclaimer"]


async def test_detail_source_url_is_exposed_for_verification() -> None:
    """AI 요약이 기사를 왜곡할 수 있으므로(실측: 부호가 뒤집힌 사례), 사용자가 원문으로 갈 수
    있는 경로를 항상 함께 준다. 승인 게이트 대신 택한 대응책이다."""
    news_id = await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get(f"/api/v1/news/{news_id}")

    assert response.json()["source_url"] == "https://kormedi.com/1/"


async def test_detail_returns_404_for_unknown_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get("/api/v1/news/999999")

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_detail_degrades_to_no_summary_when_stored_json_is_stale() -> None:
    """옛 스키마로 저장된 행이 섞여 있어도 상세화면 전체가 500이 되면 안 된다 -
    "요약 없음"으로 떨어뜨려 다음 배치의 재생성 대상이 되게 한다."""
    news_id = await _seed_news()
    async with TestSessionLocal() as session:
        news = (await session.execute(select(HealthNews).where(HealthNews.id == news_id))).scalar_one()
        news.card_summary = {"slides": [{"icon_key": "moon"}]}  # 필수 필드가 빠진 옛 모양
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.get(f"/api/v1/news/{news_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["card_summary"] is None


# ── 관리자 ───────────────────────────────────────────────────────────────────


async def test_collect_requires_admin() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.post("/api/v1/admin/news/collect")

    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_collect_saves_articles_and_reports_excluded_count(monkeypatch) -> None:
    """관리자 [뉴스 수집] 버튼. 걸러낸 수를 응답에 담는 이유: 조용히 버리면 "10건 중 6건만
    저장됨"이 필터 때문인지 파싱 실패인지 관리자가 알 수 없다."""
    article = ParsedArticle(
        source="KORMEDI",
        source_name="코메디닷컴",
        source_url="https://kormedi.com/fresh/",
        title="새 기사",
        published_at=datetime(2026, 7, 30, 10, 0, 0),
        body_text="본문입니다.",
        image_url=None,
        image_caption=None,
        source_categories=["건강"],
    )

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        return FetchResult(articles=[article], excluded=4)

    async def _fake_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary())

    monkeypatch.setattr(health_news_source_module, "fetch", _fake_fetch)
    _only_one_source(monkeypatch)
    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(card_summary_module, "generate_card_summary", _fake_summary)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _fake_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        response = await client.post("/api/v1/admin/news/collect", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["created"] == 1
    assert body["excluded"] == 4
    assert body["fetched"] == 5  # 저장 대상 1건 + 걸러낸 4건
    assert body["summaries_generated"] == 1


async def test_collect_reports_why_card_summaries_failed(monkeypatch) -> None:
    """실패 **이유**를 응답에 담아야 한다.

    (2026-07-31) 배포 환경에서 카드요약이 7건 전부 실패했는데, 응답에는 `summaries_failed=7`만
    있고 이유가 없었다. 원인은 서버 로그에만 남아서 EC2에 접속할 수 있는 사람 없이는 알 수가
    없었다. 예외 **클래스명**이 앞에 붙는 게 핵심이다 - 그것만으로 "호출 자체가 실패"와
    "LLM 출력이 스키마에 못 미침"이 갈린다."""
    article = ParsedArticle(
        source="KORMEDI",
        source_name="코메디닷컴",
        source_url="https://kormedi.com/summary-fails/",
        title="요약이 실패하는 기사",
        published_at=datetime(2026, 7, 31, 10, 0, 0),
        body_text="본문입니다.",
        image_url=None,
        image_caption=None,
        source_categories=["건강"],
    )

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        return FetchResult(articles=[article], excluded=0)

    async def _failing_summary(news, gateway=None):  # noqa: ANN001, ANN202
        raise AIWorkerUnavailableError("ai_worker 생성 실패(status=500): 내부 오류")

    _only_one_source(monkeypatch)
    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _failing_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newsfail@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/api/v1/admin/news/collect", headers=headers)
        actions = await client.get("/api/v1/admin/actions", headers=headers)

    body = response.json()
    # 요약이 실패해도 기사는 남는다(기존 설계) - 그래야 다음 실행에서 재시도된다.
    assert body["created"] == 1
    assert body["summaries_generated"] == 0
    assert body["summaries_failed"] == 1
    assert body["summaries_error"].startswith("AIWorkerUnavailableError:")
    assert "status=500" in body["summaries_error"]

    # 응답 문구는 화면을 새로 고치면 사라지므로 감사로그에도 남아야 한다.
    if actions.status_code == status.HTTP_200_OK:
        details = [a.get("detail") or "" for a in actions.json()]
        assert any("AIWorkerUnavailableError" in d for d in details)


async def test_collect_reports_no_error_when_summaries_succeed(monkeypatch) -> None:
    """성공했을 때는 오류 칸이 비어 있어야 한다 - 늘 뭔가 떠 있으면 관리자가 무시하게 된다."""
    article = ParsedArticle(
        source="KORMEDI",
        source_name="코메디닷컴",
        source_url="https://kormedi.com/summary-ok/",
        title="요약이 되는 기사",
        published_at=datetime(2026, 7, 31, 11, 0, 0),
        body_text="본문입니다.",
        image_url=None,
        image_caption=None,
        source_categories=["건강"],
    )

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        return FetchResult(articles=[article], excluded=0)

    async def _fake_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary())

    _only_one_source(monkeypatch)
    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _fake_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newsok@example.com")
        response = await client.post("/api/v1/admin/news/collect", headers={"Authorization": f"Bearer {token}"})

    assert response.json()["summaries_failed"] == 0
    assert response.json()["summaries_error"] is None


def _article(source_code: str, source_name: str) -> ParsedArticle:
    return ParsedArticle(
        source=source_code,
        source_name=source_name,
        source_url=f"https://example.test/{source_code.lower()}/1/",
        title=f"{source_name} 기사",
        published_at=datetime(2026, 7, 31, 12, 0, 0),
        body_text="본문입니다.",
        image_url=None,
        image_caption=None,
        source_categories=[],
    )


async def test_collect_adds_up_every_source(monkeypatch) -> None:
    """[뉴스 수집]은 등록된 매체를 모두 돌고 숫자를 합산한다. 매체마다 따로 누르게 하면
    관리자가 하나를 잊는다."""
    two_sources = (
        health_news_source_module.KORMEDI,
        health_news_source_module.KHEALTH,
    )
    monkeypatch.setattr(health_news_source_module, "ALL_SOURCES", two_sources)

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        return FetchResult(
            articles=[_article(source.code, source.name)],
            excluded=1,
            over_limit=3,
            unreadable=1,
        )

    async def _fake_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary())

    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _fake_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newsmulti@example.com")
        response = await client.post("/api/v1/admin/news/collect", headers={"Authorization": f"Bearer {token}"})

    body = response.json()
    assert body["created"] == 2  # 매체마다 1건
    assert body["excluded"] == 2
    assert body["over_limit"] == 6
    assert body["unreadable"] == 2
    # fetched = created + skipped + unreadable + over_limit + excluded 가 성립해야 한다 -
    # 어긋나면 어딘가에서 기사를 조용히 버리고 있다는 뜻이다.
    assert (
        body["fetched"]
        == body["created"] + body["skipped"] + body["unreadable"] + body["over_limit"] + body["excluded"]
    )
    assert body["collect_error"] is None


async def test_collect_keeps_going_when_one_source_fails(monkeypatch) -> None:
    """매체 하나의 피드가 죽어도 나머지는 수집해야 한다 - 한 곳 때문에 그날 수집분이 통째로
    빈손이 되면 손해가 크다. 대신 실패 원인은 응답에 실어 관리자가 알 수 있게 한다."""
    two_sources = (
        health_news_source_module.KORMEDI,
        health_news_source_module.KHEALTH,
    )
    monkeypatch.setattr(health_news_source_module, "ALL_SOURCES", two_sources)

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        if source.code == health_news_source_module.KORMEDI.code:
            raise httpx.ConnectError("피드에 연결할 수 없습니다")
        return FetchResult(articles=[_article(source.code, source.name)], excluded=0)

    async def _fake_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary())

    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _fake_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newspartial@example.com")
        response = await client.post("/api/v1/admin/news/collect", headers={"Authorization": f"Bearer {token}"})

    body = response.json()
    assert body["created"] == 1  # 살아있는 매체의 기사는 저장됐다
    assert body["collect_error"] is not None
    assert health_news_source_module.KORMEDI.name in body["collect_error"]
    assert "ConnectError" in body["collect_error"]


async def test_regenerate_overwrites_existing_card_summaries(monkeypatch) -> None:
    """[카드요약 다시 만들기]. 수집 배치는 요약이 **비어 있는** 기사만 고르기 때문에, 프롬프트나
    글자 수 제한을 손질하면 이미 요약이 있는 기사는 옛 기준으로 남는다. 이 버튼이 그걸 푼다."""
    news_id = await _seed_news(source_url="https://kormedi.com/regen/")

    async def _new_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary(tag="새기준"))

    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _new_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newsregen@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/api/v1/admin/news/card-summaries/regenerate", headers=headers)
        detail = await client.get(f"/api/v1/news/{news_id}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["total"] == 1
    assert body["generated"] == 1
    assert body["failed"] == 0
    assert body["summaries_error"] is None
    # 이미 있던 요약이 새 것으로 덮여야 한다(기존 배치는 이걸 건너뛴다).
    assert detail.json()["card_summary"]["slides"][0]["tag"] == "새기준"


async def test_regenerate_keeps_the_old_summary_when_generation_fails(monkeypatch) -> None:
    """**먼저 비우지 않는다.** 새로 만들기에 성공한 것만 덮어쓰므로, LLM이 실패해도 쓸 만했던
    요약을 잃지 않는다. 먼저 비우는 구현이었다면 이 테스트가 실패한다."""
    news_id = await _seed_news(source_url="https://kormedi.com/regen-fail/")

    async def _failing_summary(news, gateway=None):  # noqa: ANN001, ANN202
        raise AIWorkerUnavailableError("ai_worker 생성 실패(status=500): 내부 오류")

    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _failing_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client, email="newsregenfail@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post("/api/v1/admin/news/card-summaries/regenerate", headers=headers)
        detail = await client.get(f"/api/v1/news/{news_id}")

    body = response.json()
    assert body["generated"] == 0
    assert body["failed"] == 1
    assert body["summaries_error"].startswith("AIWorkerUnavailableError:")
    # 기존 요약이 살아 있어야 한다.
    assert detail.json()["card_summary"]["slides"][0]["tag"] == "수면"


async def test_regenerate_requires_admin() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        response = await client.post("/api/v1/admin/news/card-summaries/regenerate")

    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


async def test_collect_twice_does_not_duplicate_articles(monkeypatch) -> None:
    """같은 RSS를 여러 번 눌러도 안전해야 한다(멱등)."""
    article = ParsedArticle(
        source="KORMEDI",
        source_name="코메디닷컴",
        source_url="https://kormedi.com/same/",
        title="같은 기사",
        published_at=datetime(2026, 7, 30, 10, 0, 0),
        body_text="본문입니다.",
        image_url=None,
        image_caption=None,
        source_categories=["건강"],
    )

    async def _fake_fetch(source):  # noqa: ANN001, ANN202
        return FetchResult(articles=[article], excluded=0)

    async def _fake_summary(news, gateway=None):  # noqa: ANN001, ANN202
        return CardSummary.model_validate(_card_summary())

    _only_one_source(monkeypatch)
    monkeypatch.setattr(health_news_service_module.health_news_source, "fetch", _fake_fetch)
    monkeypatch.setattr(health_news_service_module.health_news_card_summary, "generate_card_summary", _fake_summary)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}
        first = await client.post("/api/v1/admin/news/collect", headers=headers)
        second = await client.post("/api/v1/admin/news/collect", headers=headers)

    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 1
    # 두 번째 실행은 이미 요약이 있으므로 LLM을 다시 부르지 않는다.
    assert second.json()["summaries_generated"] == 0


async def test_admin_list_exposes_source_categories_for_filter_tuning() -> None:
    """수집 필터 기준을 조정할 근거가 되므로 관리자 목록에는 RSS 카테고리를 그대로 보여준다."""
    await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        response = await client.get("/api/v1/admin/news", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["source_categories"] == ["건강", "당뇨"]


async def test_admin_can_delete_a_distorted_article() -> None:
    """승인 게이트를 두지 않기로 했으므로 삭제가 유일한 교정 수단이다."""
    news_id = await _seed_news()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        headers = {"Authorization": f"Bearer {token}"}
        deleted = await client.delete(f"/api/v1/admin/news/{news_id}", headers=headers)
        after = await client.get("/api/v1/news")

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert after.json()["items"] == []


async def test_admin_update_changes_title_only_when_sent() -> None:
    news_id = await _seed_news(title="원래 제목")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        response = await client.patch(
            f"/api/v1/admin/news/{news_id}",
            json={"title": "고친 제목"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["title"] == "고친 제목"


async def test_admin_update_returns_404_for_unknown_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=_BASE) as client:
        token = await _signup_login_admin(client)
        response = await client.patch(
            "/api/v1/admin/news/999999",
            json={"title": "없는 기사"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
