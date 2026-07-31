"""T-LLM-6: 외부 언론사 피드를 읽어 기사 한 건씩으로 바꾸는 수집기.

**본문을 어디서 얻는지가 매체마다 다르다** (2026-07-31 실측, 25개 후보):

- 코메디닷컴은 WordPress라 RSS `content:encoded`에 본문 전체 + `<img>` + `<figcaption>`이
  들어 있다. 피드 한 번으로 끝난다.
- 나머지 한국 언론사는 거의 전부 같은 CMS를 쓰는데, 그 CMS의 RSS는 **`description` 299자
  요약만** 주고 이미지도 카테고리도 주지 않는다. 대신 기사 페이지에 schema.org 표준
  `itemprop="articleBody"`가 박혀 있어서, **매체별 선택자 없이 정규식 하나로** 본문·사진·
  캡션이 온전히 뽑힌다(9개 매체에서 확인).

그래서 `NewsSourceDef.body_location`이 두 갈래를 가른다. 299자 요약만으로는 카드 3~5장을
만들 재료가 부족하고 [음성으로 듣기]가 299자만 읽고 끝나므로, 기사 페이지를 한 번 더 읽는
비용(기사 1건당 HTTP 1회, 수집 배치에서만 발생)을 치르기로 했다(2026-07-31, 박지은).

**파싱은 순수 함수로 분리해 둔다** - 네트워크를 타는 것은 `fetch()` 하나뿐이고, 나머지는
문자열을 넣어 테스트할 수 있다.

새 의존성 없이 표준 라이브러리(`xml.etree`, `html`, `re`, `urllib.parse`)로만 처리한다 -
feedparser/bs4를 넣으면 도커 재빌드가 필요해지는데, 정규식으로 충분한 것을 실측으로 확인했다.
"""

import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

# 타임존을 안 붙여 보내는 피드의 시각을 해석할 기준. 우리가 수집하는 매체가 모두 한국 언론사라
# 발행 시각은 한국 시각이다(`_parse_published_at` 주석 참고).
_PUBLISHER_TZ = ZoneInfo("Asia/Seoul")

FEED_TIMEOUT_SECONDS = 20.0
# 피드를 무한정 믿고 읽지 않는다 - 응답이 비정상적으로 크면 자른다(피드 1회는 보통 100KB 미만).
MAX_FEED_BYTES = 5 * 1024 * 1024
# 기사 페이지는 광고 스크립트가 붙어 피드보다 훨씬 크다(실측 100~250KB). 그래도 상한은 둔다.
MAX_ARTICLE_BYTES = 5 * 1024 * 1024
# 기사 페이지를 연달아 두드리지 않도록 사이에 두는 간격. 상대 서버에 대한 예의이고,
# 우리 쪽에서 급할 이유도 없다(수집은 관리자가 눌러 돌리는 배치다).
ARTICLE_FETCH_DELAY_SECONDS = 0.3

# 우리를 숨기지 않는다 - 브라우저 UA로 위장하지 않아도 두 매체 모두 정상 응답한다(실측).
USER_AGENT = "ReMedi/1.0 (+https://www.remedi-app.duckdns.org)"

# 한 번 수집할 때 매체당 가져올 기사 수. 카드요약 LLM 비용이 기사 수에 정비례하므로
# 상한이 곧 비용 상한이다(2026-07-31, 박지은: 매체당 5건). 발행일 최신순으로 고른다.
MAX_ARTICLES_PER_SOURCE = 5

# 본문에서 살릴 단락 태그. <p>만으로 두 종류의 매체 본문이 모두 온전히 복원되는 것을 실측했다.
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_FIGCAPTION_RE = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t \xa0]+")

# 기사 페이지에서 본문 영역이 시작되는 곳. schema.org 표준 microdata라 CMS 템플릿이 바뀌어도
# 살아남을 가능성이 크다. id="article-view-content-div"를 앵커로 쓰면 안 된다 - 그 문자열이
# 페이지 상단 자바스크립트(복사할 때 출처를 붙이는 코드)에 먼저 등장해서 본문을 놓친다.
_ARTICLE_BODY_ANCHOR_RE = re.compile(
    r'<(?:div|article|section)[^>]*itemprop=["\']articleBody["\'][^>]*>', re.IGNORECASE
)

# 본문이 끝나는 자리. 가장 먼저 나오는 것에서 자른다.
#   >FAQ<      : 헬스경향이 기사 끝에 붙이는 **AI 생성 Q&A 블록**. 기사 내용을 되풀이하는
#                문답이라 카드요약 재료로도 나쁘고, [음성으로 듣기]가 같은 말을 두 번 읽는다.
#   </article> : 본문 요소의 끝. 이 뒤는 관련기사·추천기사다.
#   저작권자/무단전재 : 본문 바로 뒤에 오는 저작권 문구.
_ARTICLE_END_RES = (
    re.compile(r">\s*FAQ\s*<", re.IGNORECASE),
    re.compile(r"</article>", re.IGNORECASE),
    re.compile(r"저작권자"),
    re.compile(r"무단전재"),
)

# 본문이 아닌 단락. 단락 단위로 걸러낸다.
#   appeared first on / The post : RSS description 끝에 WordPress가 붙이는 자기 홍보 문구.
#   저작권자/무단전재/Copyright  : 위 구조 기준을 빠져나온 저작권 문구를 한 번 더 막는다.
_BOILERPLATE_MARKERS = ("appeared first on", "The post ", "저작권자", "무단전재", "Copyright")


class BodyLocation(StrEnum):
    """기사 본문을 어디서 얻는가."""

    # RSS content:encoded 안에 본문 전체가 들어있다. 피드 한 번으로 끝난다(코메디닷컴).
    FEED = "feed"
    # RSS는 요약만 준다 - 기사 페이지를 한 번 더 읽어야 본문·사진이 나온다.
    ARTICLE_PAGE = "article_page"


@dataclass(frozen=True)
class NewsSourceDef:
    """매체 하나의 정의. 소스를 늘릴 때 이 값만 추가하면 되고, 수집 서비스는 어떤 매체인지
    몰라도 된다."""

    code: str
    name: str
    feed_url: str
    # 이 카테고리가 하나라도 붙은 기사는 건강정보가 아니므로 저장하지 않는다.
    # CMS 계열 매체의 피드는 `<category>`를 아예 주지 않아 이 필터를 쓸 수 없다 - 그쪽은
    # 대신 **섹션 피드를 골라 받는 것**이 필터 역할을 한다(아래 KHEALTH 주석 참고).
    excluded_categories: frozenset[str]
    body_location: BodyLocation = BodyLocation.FEED


KORMEDI = NewsSourceDef(
    code="KORMEDI",
    name="코메디닷컴",
    # 끝의 슬래시가 없으면 301이 뜬다 - follow_redirects와 함께 두 겹으로 막아둔다.
    feed_url="https://kormedi.com/feed/",
    # 실측(2026-07-30) 결과 코메디 피드 10건 중 4건이 건강정보가 아니었다:
    #   "AI 공시뉴스"   → 상장사 분기실적/주총 공시(예: "일동제약 2분기 영업이익 50억")
    #   "바이오·제약"   → 제약사 파이프라인 뉴스(예: "올릭스 비만약 후보 원숭이 실험")
    # 둘 다 투자자용 기사라 우리 사용자에게 의미가 없다.
    # 반면 "기획ㆍ연재-셀럽헬스"(연예인 건강)는 남겨둔다 - 다이어트/식단 같은 실제 생활 팁이
    # 담기는 경우가 있고, 사진과 제목이 화려해 피드를 생기있게 만든다(2026-07-30 결정).
    excluded_categories=frozenset({"AI 공시뉴스", "바이오·제약"}),
    body_location=BodyLocation.FEED,
)

KHEALTH = NewsSourceDef(
    code="KHEALTH",
    name="헬스경향",
    # **전체기사(allArticle.xml)가 아니라 "건강정보" 섹션 피드다.** 이 CMS는 `<category>`를
    # 주지 않아 코메디처럼 카테고리로 걸러낼 수 없는데, 섹션 피드를 고르면 그 자체가 필터가
    # 된다. 실측(2026-07-31) 이 섹션 최신 10건은 전부 일반인 건강정보였다(일회용 안약 재사용
    # 위험, 캄필로박터균 급증, 주방 연기와 폐암, 휴가철 식중독 예방).
    # 전체기사 쪽은 병원 홍보·의료정책이 절반이라 쓰지 않는다.
    feed_url="https://www.k-health.com/rss/S1N10.xml",
    excluded_categories=frozenset(),
    body_location=BodyLocation.ARTICLE_PAGE,
)

KHLOG = NewsSourceDef(
    code="KHLOG",
    name="코리아헬스로그",
    # "News" 섹션. 질환을 차분히 설명하는 기사가 많아 카드뉴스로 만들기 좋다(전립선염 신호,
    # 폐암 치료법, 온열질환). 다만 실측 상위 5건 중 1~2건은 의료정책 기사가 섞인다
    # (예: "마약류취급자 불법사용 검사 근거 신설"). 이 매체의 "희귀질환&암"(S1N12) 섹션은
    # 더 깨끗하지만 한 달에 8~10건뿐이라 최신순 상한에서 거의 밀린다 - 필요해지면 별도
    # 소스로 추가하면 된다.
    feed_url="https://www.koreahealthlog.com/rss/S1N1.xml",
    excluded_categories=frozenset(),
    body_location=BodyLocation.ARTICLE_PAGE,
)

# 수집 대상 전체. 매체를 늘리려면 위에 정의를 하나 추가하고 여기에 넣으면 된다.
ALL_SOURCES: tuple[NewsSourceDef, ...] = (KORMEDI, KHEALTH, KHLOG)


@dataclass(frozen=True)
class FeedEntry:
    """피드 item 하나에서 뽑은 **기사 식별 정보**. 본문은 아직 없다.

    본문을 여기 넣지 않는 이유: CMS 계열 매체는 이 시점에 본문을 모른다(기사 페이지를 아직
    읽지 않았다). 반쯤 빈 `ParsedArticle`을 돌려주는 대신 단계를 나눈다 - 그래야 "걸러내기"와
    "상한 적용"을 기사 페이지를 읽기 **전에** 할 수 있고, 버릴 기사에 HTTP를 쓰지 않는다.
    """

    source_url: str
    title: str
    published_at: datetime
    source_categories: list[str]
    # RSS content:encoded 원문. CMS 계열 매체는 이게 없어서 빈 문자열이다.
    encoded_html: str


@dataclass(frozen=True)
class ArticleContent:
    """기사 한 건의 읽을 거리. 피드에서 뽑았는지 기사 페이지에서 뽑았는지는 여기 남지 않는다."""

    body_text: str
    image_url: str | None
    image_caption: str | None


@dataclass(frozen=True)
class ParsedArticle:
    """저장 직전의 기사 한 건. DB 모델과 1:1은 아니다(id/fetched_at 등은 없음)."""

    source: str
    source_name: str
    source_url: str
    title: str
    published_at: datetime
    body_text: str
    image_url: str | None
    image_caption: str | None
    source_categories: list[str]


def _strip_tags(fragment: str) -> str:
    """HTML 조각 → 평문. 태그를 지우고 엔티티(&#8230; 등)를 실제 글자로 되돌린다."""
    text = _TAG_RE.sub("", fragment)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _extract_body_text(fragment: str) -> str:
    """HTML 조각 → 단락 사이를 빈 줄로 구분한 평문 본문."""
    paragraphs = []
    for raw in _PARAGRAPH_RE.findall(fragment):
        text = _strip_tags(raw)
        if not text:
            continue
        if any(marker in text for marker in _BOILERPLATE_MARKERS):
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _truncate(value: str | None, limit: int) -> str | None:
    """DB 컬럼 길이를 넘는 값이 오면 잘라서 저장한다 - 기사 한 건 때문에 수집 전체가
    실패하는 것보다 낫다(제목/캡션은 잘려도 읽을 수 있다)."""
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


def _extract_content(fragment: str, *, base_url: str) -> ArticleContent | None:
    """HTML 조각에서 본문·대표사진·캡션을 뽑는다. 본문이 비면 None(그 기사는 버린다).

    이미지 주소를 `base_url` 기준으로 절대 URL로 만든다 - 어떤 매체는 `/news/photo/...`
    처럼 상대경로로 주는데, 그대로 저장하면 우리 도메인 기준으로 해석돼 사진이 깨진다.
    """
    body_text = _extract_body_text(fragment)
    if not body_text:
        return None

    image_match = _IMG_SRC_RE.search(fragment)
    caption_match = _FIGCAPTION_RE.search(fragment)
    caption = _strip_tags(caption_match.group(1)) if caption_match else None
    return ArticleContent(
        body_text=body_text,
        image_url=_truncate(urljoin(base_url, image_match.group(1)), 500) if image_match else None,
        image_caption=_truncate(caption, 500) if caption else None,
    )


def extract_feed_content(entry: FeedEntry) -> ArticleContent | None:
    """RSS `content:encoded`에서 본문을 뽑는다(코메디닷컴 방식)."""
    if not entry.encoded_html:
        return None
    return _extract_content(entry.encoded_html, base_url=entry.source_url)


def extract_article_page_content(page_html: str, article_url: str) -> ArticleContent | None:
    """기사 페이지 HTML에서 본문을 뽑는다(CMS 계열 매체 방식).

    HTML을 그대로 저장하지 않고 평문으로 뽑는 이유는 `app/models/health_news.py`의
    `body_text` 주석 참고(제3자 HTML 주입 통로를 만들지 않기 위함).
    """
    anchor = _ARTICLE_BODY_ANCHOR_RE.search(page_html)
    if anchor is None:
        return None
    rest = page_html[anchor.end() :]

    # 본문 끝 표시 중 가장 먼저 나오는 것에서 자른다. 하나도 없으면(템플릿이 바뀐 경우)
    # 조각 전체를 쓰되, 단락 필터가 저작권 문구를 한 번 더 막는다.
    ends = [m.start() for m in (pattern.search(rest) for pattern in _ARTICLE_END_RES) if m is not None]
    fragment = rest[: min(ends)] if ends else rest
    return _extract_content(fragment, base_url=article_url)


def _parse_published_at(raw: str) -> datetime | None:
    """발행일 문자열 → **timezone 없는 UTC** datetime. 형식을 알아볼 수 없으면 None.

    `published_at` 컬럼이 timezone 없는 DATETIME이라, 어떤 매체가 들어와도 같은 기준(UTC)으로
    맞춰 넣어야 한다. 안 맞추면 피드 정렬(발행일 최신순)에서 매체끼리 시각이 어긋난다.

    두 형식을 모두 받아야 한다(2026-07-31 실측):
      - `Thu, 30 Jul 2026 07:21:04 +0000` : RSS 표준(RFC 2822). 코메디닷컴.
      - `2026-07-31 17:15:31`             : CMS 계열 매체. **타임존이 없고 한국 시각이다.**
        이걸 그대로 저장하면 코메디 기사보다 9시간 미래로 보여서 피드 맨 위를 늘 차지한다.
    """
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            # 타임존이 없으므로 발행사의 현지 시각(한국)으로 해석한다. 우리 앱의 타임존이 아니라
            # **그 매체의** 타임존이라서 config가 아니라 여기 못박아 둔다.
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_PUBLISHER_TZ)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        # RFC 2822인데 타임존이 빠진 경우(예: "Thu, 30 Jul 2026 07:21:04"). 위와 같은 이유로
        # 발행사 현지 시각으로 본다.
        parsed = parsed.replace(tzinfo=_PUBLISHER_TZ)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def parse_feed(xml_text: str) -> list[FeedEntry]:
    """RSS XML 문자열 → 기사 항목 목록. 개별 item이 깨져 있으면 그 item만 조용히 건너뛴다
    (필수 필드가 없는 한 건 때문에 나머지 9건을 못 받으면 손해가 크다)."""
    # 표준 xml.etree는 외부에서 받은 XML의 엔티티 폭탄(billion laughs)에 취약하다. 그 공격은
    # 반드시 문서 안에 DOCTYPE으로 엔티티를 선언해야 하고, 정상 RSS에는 DOCTYPE이 없다.
    # 그래서 DOCTYPE이 보이면 파싱 전에 거절한다 - defusedxml을 새로 넣지 않고 막는 방법.
    # (응답 크기 제한만으로는 못 막는다 - 작은 파일이 파싱 중에 폭발하는 공격이라서.)
    if "<!DOCTYPE" in xml_text[:2048].upper() or "<!ENTITY" in xml_text.upper():
        raise ValueError("RSS에 DOCTYPE/ENTITY 선언이 있습니다 - 정상 피드가 아니므로 파싱하지 않습니다.")
    root = ET.fromstring(xml_text)
    entries: list[FeedEntry] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        if not (title and link and pub_date_raw):
            continue
        published_at = _parse_published_at(pub_date_raw)
        if published_at is None:
            continue

        entries.append(
            FeedEntry(
                source_url=link[:500],
                # 제목 앞에 BOM(﻿)을 붙여 보내는 매체가 있다(정신의학신문 실측) -
                # 화면에서 빈 칸처럼 보이고 음성읽기에서도 잡음이 되므로 여기서 떼어낸다.
                title=_truncate(html.unescape(title).replace("﻿", "").strip(), 300) or "",
                published_at=published_at,
                source_categories=[c.text.strip() for c in item.findall("category") if c.text and c.text.strip()],
                encoded_html=item.findtext("content:encoded", namespaces=_NS) or "",
            )
        )
    return entries


@dataclass(frozen=True)
class SelectResult:
    """걸러내기 결과. 걸러낸 수를 함께 돌려주는 이유: 조용히 버리면 "10건 중 6건만 남음"이
    파싱 실패인지 필터인지 구분이 안 된다."""

    entries: list[FeedEntry]
    excluded: int


def select_relevant(entries: list[FeedEntry], source: NewsSourceDef) -> SelectResult:
    """건강정보가 아닌 기사를 걸러낸다. 걸러진 기사는 저장하지 않는다 - 쓸데없는 행이
    테이블에 안 쌓이고, 카드요약 LLM 호출도 낭비되지 않는다."""
    kept = [e for e in entries if not (source.excluded_categories & set(e.source_categories))]
    return SelectResult(entries=kept, excluded=len(entries) - len(kept))


def take_latest(entries: list[FeedEntry], limit: int = MAX_ARTICLES_PER_SOURCE) -> tuple[list[FeedEntry], int]:
    """발행일 최신순으로 상한만큼 고른다. 남긴 목록과 상한 때문에 미룬 수를 함께 돌려준다.

    피드가 대개 최신순으로 오지만 믿지 않고 직접 정렬한다 - 순서가 뒤집힌 피드에서 상한을
    적용하면 옛 기사만 골라오게 된다.
    """
    ordered = sorted(entries, key=lambda e: e.published_at, reverse=True)
    return ordered[:limit], max(0, len(ordered) - limit)


def build_article(entry: FeedEntry, content: ArticleContent, source: NewsSourceDef) -> ParsedArticle:
    """항목 + 본문 → 저장할 기사 한 건."""
    return ParsedArticle(
        source=source.code,
        source_name=source.name,
        source_url=entry.source_url,
        title=entry.title,
        published_at=entry.published_at,
        body_text=content.body_text,
        image_url=content.image_url,
        image_caption=content.image_caption,
        source_categories=entry.source_categories,
    )


@dataclass(frozen=True)
class FetchResult:
    """수집 1회에서 수집기가 내놓는 것. 버린 것을 모두 숫자로 보고한다 - 조용히 버리면
    "20건 중 5건만 저장됨"의 이유를 관리자가 알 수 없다."""

    articles: list[ParsedArticle]  # 저장 대상
    excluded: int  # 건강정보가 아닌 카테고리라 버린 수
    over_limit: int = 0  # 매체당 상한을 넘어 이번에는 가져오지 않은 수(다음 수집에서 후보가 된다)
    unreadable: int = 0  # 본문을 뽑지 못해 버린 수. 계속 늘면 상대 매체의 템플릿이 바뀐 것이다


async def _read(client: httpx.AsyncClient, url: str, *, max_bytes: int) -> str:
    response = await client.get(url)
    response.raise_for_status()
    if len(response.content) > max_bytes:
        raise ValueError(f"응답이 너무 큽니다({len(response.content)} bytes) - {url}")
    return response.text


async def _content_for(client: httpx.AsyncClient, entry: FeedEntry, source: NewsSourceDef) -> ArticleContent | None:
    """기사 한 건의 본문을 얻는다. 기사 페이지를 읽어야 하는 매체는 여기서 HTTP를 한 번 더 쓴다.

    한 건이 실패해도 예외를 밖으로 내지 않는다 - 기사 하나 때문에 그 매체 수집 전체가
    빈손이 되면 손해가 크다(호출자가 `unreadable`로 센다).
    """
    if source.body_location is BodyLocation.FEED:
        return extract_feed_content(entry)

    try:
        page = await _read(client, entry.source_url, max_bytes=MAX_ARTICLE_BYTES)
    except (httpx.HTTPError, ValueError):
        logger.warning("기사 페이지를 읽지 못했습니다 (%s)", entry.source_url, exc_info=True)
        return None
    return extract_article_page_content(page, entry.source_url)


async def fetch(source: NewsSourceDef) -> FetchResult:
    """매체 하나를 실제로 수집한다. 네트워크가 닿는 유일한 함수 - 테스트는 `parse_feed`/
    `select_relevant`/`extract_*`를 직접 호출해 이 함수를 우회한다.

    순서가 중요하다: 걸러내기와 상한 적용을 **기사 페이지를 읽기 전에** 한다. 그래야 저장하지
    않을 기사에 HTTP를 쓰지 않는다.
    """
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=FEED_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
        xml_text = await _read(client, source.feed_url, max_bytes=MAX_FEED_BYTES)
        selected = select_relevant(parse_feed(xml_text), source)
        targets, over_limit = take_latest(selected.entries)

        articles: list[ParsedArticle] = []
        unreadable = 0
        for index, entry in enumerate(targets):
            if index > 0 and source.body_location is BodyLocation.ARTICLE_PAGE:
                await asyncio.sleep(ARTICLE_FETCH_DELAY_SECONDS)
            content = await _content_for(client, entry, source)
            if content is None:
                unreadable += 1
                continue
            articles.append(build_article(entry, content, source))

    return FetchResult(articles=articles, excluded=selected.excluded, over_limit=over_limit, unreadable=unreadable)
