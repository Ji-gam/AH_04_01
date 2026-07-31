"""T-LLM-6: 수집 오케스트레이션. RSS 파서(`health_news_source`)와 저장소를 이어붙인다.

**수집과 카드요약은 두 단계로 나눠 실행한다.** 카드요약은 LLM에 의존해 느리고 실패할 수 있어서,
한 몸으로 묶으면 OpenAI가 흔들릴 때 기사 저장까지 같이 실패한다. 그래서
`collect()`로 기사를 먼저 다 저장하고, `generate_missing_card_summaries()`가 요약이 빈 기사만
따로 채운다 - 중간에 실패해도 다음 실행이 빠진 것만 다시 시도한다.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.health_news_dto import (
    CardSummary,
    HealthNewsDetailResponse,
    HealthNewsFeedItem,
)
from app.models.health_news import HealthNews
from app.repositories.health_news_repository import HealthNewsRepository
from app.services import health_news_card_summary, health_news_source
from app.services.health_news_source import ParsedArticle
from app.services.safety_service import DISCLAIMER_TEXT

logger = logging.getLogger(__name__)

# 피드 한 번에 내려줄 기본 개수. 기사가 쌓여도 첫 화면이 무거워지지 않게 상한을 둔다.
DEFAULT_FEED_LIMIT = 30


@dataclass
class CollectResult:
    """수집 1회의 결과. 관리자 화면이 이 숫자를 그대로 보여준다.

    `fetched = created + skipped + unreadable + over_limit + excluded` 가 항상 성립한다 -
    숫자가 맞지 않으면 어딘가에서 기사를 조용히 버리고 있다는 뜻이다.
    """

    fetched: int  # 피드에서 파싱된 기사 수(여러 매체를 돌면 합계)
    excluded: int  # 건강정보가 아닌 카테고리라 버린 수
    created: int  # 새로 저장한 수
    skipped: int  # 이미 있어서 건너뛴 수
    # 매체당 상한(MAX_ARTICLES_PER_SOURCE)을 넘어 이번에는 가져오지 않은 수. 버린 게 아니라
    # 미룬 것이다 - 다음 수집에서 다시 후보가 된다.
    over_limit: int = 0
    # 본문을 뽑지 못해 버린 수. 0이 정상이고, 계속 늘면 상대 매체의 기사 페이지 구조가 바뀐 것이다.
    unreadable: int = 0
    # 매체 하나가 통째로 실패한 첫 원인 한 줄(피드가 죽었거나 형식이 깨진 경우).
    # 실패해도 나머지 매체는 계속 수집하므로, 원인은 이 값으로만 드러난다.
    first_error: str | None = None


@dataclass
class SaveOutcome:
    """저장 단계만의 결과. 수집 전체 결과(`CollectResult`)와 섞지 않는다 - 저장 단계는
    걸러낸 수나 상한을 모른다(이미 걸러진 목록만 받는다)."""

    created: int
    skipped: int


# 관리자 화면·감사로그에 실을 오류 설명의 최대 길이. 전체 트레이스백은 서버 로그에만 남긴다.
_ERROR_DETAIL_MAX_CHARS = 300


def _describe_error(exc: Exception) -> str:
    """예외를 한 줄로 요약한다. **클래스명을 앞에 붙이는 게 핵심**이다 - 그것만으로 원인이 갈린다.

    - `AIWorkerUnavailableError` → ai_worker 호출 자체가 실패(연결/타임아웃/상태코드)
    - `ValidationError` → 호출은 됐지만 LLM 출력이 스키마(슬라이드 최소 개수 등)에 못 미침
    """
    message = f"{type(exc).__name__}: {exc}".replace("\n", " ")
    if len(message) <= _ERROR_DETAIL_MAX_CHARS:
        return message
    return message[:_ERROR_DETAIL_MAX_CHARS] + "…"


@dataclass
class SummaryResult:
    """카드요약 생성 1회의 결과."""

    pending: int  # 요약이 비어 있던 기사 수
    generated: int  # 새로 요약을 채운 수
    failed: int  # LLM 실패로 못 채운 수(다음 실행에서 재시도된다)
    # 첫 실패의 원인 한 줄. (2026-07-31) 실패 원인이 서버 로그에만 남아서, EC2에 SSH할 수 있는
    # 리더 없이는 "7건 실패"의 이유를 알 수 없었다. 실패를 삼키는 설계(아래 주석 참고)를
    # 유지하면서도 원인은 관리자가 볼 수 있어야 한다.
    first_error: str | None = None


class HealthNewsService:
    def __init__(self, repo: HealthNewsRepository | None = None) -> None:
        self._repo = repo or HealthNewsRepository()

    async def collect(self, session: AsyncSession, source: health_news_source.NewsSourceDef) -> CollectResult:
        """매체 하나를 1회 수집한다. 어떤 매체인지는 인자로 받는다 - 이 메서드는 매체가
        코메디인지 헬스경향인지 모른다."""
        fetched = await health_news_source.fetch(source)
        saved = await self._save_articles(session, fetched.articles)
        return CollectResult(
            fetched=len(fetched.articles) + fetched.excluded + fetched.over_limit + fetched.unreadable,
            excluded=fetched.excluded,
            created=saved.created,
            skipped=saved.skipped,
            over_limit=fetched.over_limit,
            unreadable=fetched.unreadable,
        )

    async def collect_all(
        self,
        session: AsyncSession,
        sources: tuple[health_news_source.NewsSourceDef, ...] | None = None,
    ) -> CollectResult:
        """모든 매체를 1회 수집해 결과를 합산한다. 관리자 [뉴스 수집] 버튼과 수동 트리거
        스크립트가 호출한다.

        **매체 하나가 실패해도 나머지는 계속 수집한다** - 한 매체의 피드가 죽었다고 그날
        수집분이 통째로 빈손이 되면 손해가 크다. 실패 원인은 `first_error`로 올려보낸다
        (카드요약 배치가 기사 단위로 실패를 다루는 것과 같은 방식).

        `sources`의 기본값을 인자 자리에 두지 않고 여기서 읽는 이유: 기본 인자는 함수가 정의될
        때 한 번 묶이므로, 테스트가 `ALL_SOURCES`를 바꿔치기해도 반영되지 않는다.
        """
        targets = sources if sources is not None else health_news_source.ALL_SOURCES
        total = CollectResult(fetched=0, excluded=0, created=0, skipped=0)
        for source in targets:
            try:
                one = await self.collect(session, source)
            except Exception as e:
                logger.exception("매체 수집 실패 (source=%s)", source.code)
                if total.first_error is None:
                    total.first_error = f"{source.name} - {_describe_error(e)}"
                continue
            total.fetched += one.fetched
            total.excluded += one.excluded
            total.created += one.created
            total.skipped += one.skipped
            total.over_limit += one.over_limit
            total.unreadable += one.unreadable
            logger.info(
                "수집 완료 source=%s fetched=%d created=%d skipped=%d over_limit=%d unreadable=%d",
                source.code,
                one.fetched,
                one.created,
                one.skipped,
                one.over_limit,
                one.unreadable,
            )
        return total

    async def _save_articles(self, session: AsyncSession, articles: list[ParsedArticle]) -> SaveOutcome:
        """이미 있는 기사(source + source_url)는 건너뛴다.

        DB 유니크 제약이 최종 방어선이지만, 조회로 먼저 걸러서 건너뛴 수를 세고 무의미한
        INSERT 실패를 만들지 않는다. 같은 RSS를 몇 번 돌려도 결과가 같아야 한다(멱등)."""
        created = 0
        skipped = 0
        for article in articles:
            existing = await self._repo.get_by_source_url(session, article.source, article.source_url)
            if existing is not None:
                skipped += 1
                continue
            await self._repo.save(
                session,
                source=article.source,
                source_name=article.source_name,
                source_url=article.source_url,
                title=article.title,
                published_at=article.published_at,
                body_text=article.body_text,
                image_url=article.image_url,
                image_caption=article.image_caption,
                source_categories=article.source_categories,
            )
            created += 1
        return SaveOutcome(created=created, skipped=skipped)

    async def generate_missing_card_summaries(self, session: AsyncSession, limit: int | None = None) -> SummaryResult:
        """카드요약이 아직 없는 기사들의 요약을 만들어 채운다.

        기사 한 건이 실패해도 나머지는 계속 처리한다 - 한 건의 LLM 오류로 배치 전체가 멈추면
        그날 수집분이 통째로 요약 없는 상태가 된다. 실패한 기사는 `card_summary`가 그대로
        비어 있으므로 다음 실행에서 자동으로 다시 시도된다."""
        pending = await self._repo.list_missing_card_summary(session, limit=limit)
        return await self._fill_card_summaries(session, pending)

    async def regenerate_card_summaries(self, session: AsyncSession, limit: int | None = None) -> SummaryResult:
        """**모든** 기사의 카드요약을 다시 만든다. 관리자 [카드요약 다시 만들기] 버튼.

        프롬프트나 글자 수 제한을 손질하면 기존 기사에도 새 기준을 적용해야 하는데, 평소
        배치는 요약이 비어 있는 기사만 고르기 때문에(`list_missing_card_summary`) 이미 있는
        기사는 영원히 옛 기준으로 남는다.

        **기존 요약을 먼저 지우지 않는다.** 새로 만들기를 시도하고 성공한 것만 덮어쓴다 -
        먼저 비우면 LLM이 중간에 실패했을 때 쓸 만했던 요약까지 잃는다."""
        targets = await self._repo.list_all_for_card_summary(session, limit=limit)
        return await self._fill_card_summaries(session, targets)

    async def _fill_card_summaries(self, session: AsyncSession, targets: list[HealthNews]) -> SummaryResult:
        """받은 기사들의 카드요약을 만들어 채운다. 신규 생성과 재생성이 공유한다.

        기사 한 건이 실패해도 나머지는 계속 처리한다 - 한 건의 LLM 오류로 배치 전체가 멈추면
        그날 수집분이 통째로 요약 없는 상태가 된다. 실패한 기사는 기존 값이 그대로 남으므로
        (신규라면 비어 있는 상태) 다음 실행에서 자동으로 다시 시도된다."""
        generated = 0
        failed = 0
        first_error: str | None = None
        for news in targets:
            try:
                summary = await health_news_card_summary.generate_card_summary(news)
            except Exception as e:
                # 실패 원인(LLM 응답 형식, OpenAI 장애, 스키마 하한 미달 등)을 남기고 다음 기사로.
                logger.exception("카드요약 생성 실패 (news_id=%s)", news.id)
                failed += 1
                # 첫 실패만 들고 나간다. 전부 같은 이유로 실패하는 경우가 대부분이라 한 줄이면
                # 원인 파악에 충분하고, 기사 수만큼 메시지를 쌓으면 응답이 지저분해진다.
                if first_error is None:
                    first_error = _describe_error(e)
                continue
            await self._repo.set_card_summary(session, news, summary.model_dump())
            generated += 1
        return SummaryResult(pending=len(targets), generated=generated, failed=failed, first_error=first_error)

    # ── 조회 ──────────────────────────────────────────────────────────────────

    async def get_feed(self, session: AsyncSession, limit: int | None = None) -> list[HealthNewsFeedItem]:
        """건강정보 화면의 뉴스 피드. 1단계는 개인화 없이 발행일 최신순이다(질환 태깅은 2단계).

        요약이 아직 없는 기사도 피드에는 보여준다 - 원문은 이미 읽을 수 있으므로 감출 이유가
        없고, `has_card_summary`로 [카드요약보기] 버튼만 비활성으로 두면 된다."""
        rows = await self._repo.list_feed(session, limit=limit or DEFAULT_FEED_LIMIT)
        return [
            HealthNewsFeedItem(
                id=n.id,
                title=n.title,
                source_name=n.source_name,
                source_url=n.source_url,
                published_at=n.published_at,
                image_url=n.image_url,
                has_card_summary=n.card_summary is not None,
            )
            for n in rows
        ]

    async def get_detail(self, session: AsyncSession, news_id: int) -> HealthNewsDetailResponse | None:
        """상세화면. 카드요약을 함께 실어 보내므로 [카드요약보기]에 추가 요청이 없다
        (TRD T-LLM-4의 "별도 대기 없이")."""
        news = await self._repo.get_by_id(session, news_id)
        if news is None:
            return None
        return HealthNewsDetailResponse(
            id=news.id,
            title=news.title,
            source_name=news.source_name,
            source_url=news.source_url,
            published_at=news.published_at,
            body_text=news.body_text,
            image_url=news.image_url,
            image_caption=news.image_caption,
            card_summary=self._parse_card_summary(news),
            # 면책 문구는 DB에 저장하지 않고 응답 시점에 붙인다 - 문구가 바뀌면 기존 기사까지
            # 한 번에 반영돼야 하기 때문(REQ-INFO-004).
            disclaimer=DISCLAIMER_TEXT,
        )

    @staticmethod
    def _parse_card_summary(news: HealthNews) -> CardSummary | None:
        """저장된 JSON을 스키마로 되돌린다. 옛 스키마로 저장된 행이 섞여 있어도 상세화면 전체가
        500이 되지 않게, 검증 실패는 "요약 없음"으로 떨어뜨린다(재생성 대상이 된다)."""
        if news.card_summary is None:
            return None
        try:
            return CardSummary.model_validate(news.card_summary)
        except ValueError:
            logger.warning("저장된 카드요약이 현재 스키마와 맞지 않습니다 (news_id=%s)", news.id)
            return None
