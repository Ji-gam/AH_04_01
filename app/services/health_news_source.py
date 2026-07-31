"""T-LLM-6: 외부 언론사 RSS를 읽어 기사 한 건씩으로 바꾸는 파서.

**여기는 순수 파싱만 한다** - DB도 LLM도 모른다. 그래야 소스를 늘릴 때(7단계) 이 파일만
건드리면 되고, 테스트도 네트워크 없이 XML 문자열만 넣어 돌릴 수 있다.

RSS의 `content:encoded`는 HTML이지만 **HTML을 그대로 넘기지 않고 평문으로 뽑는다** - 이유는
`app/models/health_news.py`의 `body_text` 주석 참고(제3자 HTML 주입 통로를 만들지 않기 위함).

새 의존성 없이 표준 라이브러리(`xml.etree`, `html`, `re`)로만 처리한다 - feedparser/bs4를 넣으면
도커 재빌드가 필요해지는데, RSS 구조가 단순해서 그만한 값을 하지 않는다.
"""

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

FEED_TIMEOUT_SECONDS = 20.0
# RSS를 무한정 믿고 읽지 않는다 - 응답이 비정상적으로 크면 자른다(피드 1회는 보통 100KB 미만).
MAX_FEED_BYTES = 5 * 1024 * 1024

# 본문에서 살릴 단락 태그. <p>만으로 코메디 본문이 온전히 복원되는 것을 실측으로 확인했다.
_PARAGRAPH_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_FIGCAPTION_RE = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t ]+")

# RSS description 끝에 WordPress가 항상 붙이는 자기 홍보 문구. 본문에 섞이면 카드요약 품질이
# 떨어지므로 단락 단위로 걸러낸다.
_BOILERPLATE_MARKERS = ("appeared first on", "The post ")


@dataclass(frozen=True)
class NewsSourceDef:
    """매체 하나의 정의. 소스를 늘릴 때(7단계) 이 값만 추가하면 되고, 수집 서비스는
    어떤 매체인지 몰라도 된다."""

    code: str
    name: str
    feed_url: str
    # 이 카테고리가 하나라도 붙은 기사는 건강정보가 아니므로 저장하지 않는다.
    excluded_categories: frozenset[str]


# 코메디닷컴은 WordPress 기반이라 content:encoded에 본문 전체 + <img> + <figcaption>이 들어있다.
# 그래서 기사 페이지를 따로 긁을 필요가 없다(스크래핑 0회). 후보 중 제대로 된
# application/rss+xml을 준 유일한 매체이기도 하다(2026-07-30 실측).
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
)


@dataclass(frozen=True)
class ParsedArticle:
    """RSS item 하나를 우리 필드로 정리한 결과. DB 모델과 1:1은 아니다(id/fetched_at 등은 없음)."""

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


def _extract_body_text(encoded_html: str) -> str:
    """content:encoded → 단락 사이를 빈 줄로 구분한 평문 본문."""
    paragraphs = []
    for raw in _PARAGRAPH_RE.findall(encoded_html):
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


def parse_feed(xml_text: str, *, source: str, source_name: str) -> list[ParsedArticle]:
    """RSS XML 문자열 → 기사 목록. 개별 item이 깨져 있으면 그 item만 조용히 건너뛴다
    (필수 필드가 없는 한 건 때문에 나머지 9건을 못 받으면 손해가 크다)."""
    # 표준 xml.etree는 외부에서 받은 XML의 엔티티 폭탄(billion laughs)에 취약하다. 그 공격은
    # 반드시 문서 안에 DOCTYPE으로 엔티티를 선언해야 하고, 정상 RSS에는 DOCTYPE이 없다.
    # 그래서 DOCTYPE이 보이면 파싱 전에 거절한다 - defusedxml을 새로 넣지 않고 막는 방법.
    # (응답 크기 제한만으로는 못 막는다 - 작은 파일이 파싱 중에 폭발하는 공격이라서.)
    if "<!DOCTYPE" in xml_text[:2048].upper() or "<!ENTITY" in xml_text.upper():
        raise ValueError("RSS에 DOCTYPE/ENTITY 선언이 있습니다 - 정상 피드가 아니므로 파싱하지 않습니다.")
    root = ET.fromstring(xml_text)
    articles: list[ParsedArticle] = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        encoded = item.findtext("content:encoded", namespaces=_NS) or ""
        if not (title and link and pub_date_raw and encoded):
            continue
        try:
            published_at = parsedate_to_datetime(pub_date_raw)
        except (TypeError, ValueError):
            continue
        body_text = _extract_body_text(encoded)
        if not body_text:
            continue

        image_match = _IMG_SRC_RE.search(encoded)
        caption_match = _FIGCAPTION_RE.search(encoded)
        caption = _strip_tags(caption_match.group(1)) if caption_match else None

        articles.append(
            ParsedArticle(
                source=source,
                source_name=source_name,
                source_url=link[:500],
                title=_truncate(html.unescape(title), 300) or "",
                # DB의 published_at은 timezone 없는 DATETIME이므로 tz 정보를 떼서 넣는다.
                # RSS는 +0000(UTC)로 주므로 UTC 기준 시각이 그대로 저장된다.
                published_at=published_at.replace(tzinfo=None),
                body_text=body_text,
                image_url=_truncate(image_match.group(1), 500) if image_match else None,
                image_caption=_truncate(caption, 500) if caption else None,
                source_categories=[c.text.strip() for c in item.findall("category") if c.text and c.text.strip()],
            )
        )
    return articles


@dataclass(frozen=True)
class FetchResult:
    """수집 1회에서 파서가 내놓는 것. 걸러낸 수를 함께 돌려주는 이유: 조용히 버리면
    "10건 중 6건만 저장됨"이 파싱 실패인지 필터인지 구분이 안 된다."""

    articles: list[ParsedArticle]  # 저장 대상
    excluded: int  # 건강정보가 아닌 카테고리라 버린 수


def select_relevant(articles: list[ParsedArticle], source: NewsSourceDef) -> FetchResult:
    """건강정보가 아닌 기사를 걸러낸다. 걸러진 기사는 저장하지 않는다 - 쓸데없는 행이
    테이블에 안 쌓이고, 카드요약 LLM 호출도 낭비되지 않는다."""
    kept = [a for a in articles if not (source.excluded_categories & set(a.source_categories))]
    return FetchResult(articles=kept, excluded=len(articles) - len(kept))


async def fetch(source: NewsSourceDef) -> FetchResult:
    """RSS를 실제로 받아 파싱하고 걸러낸다. 네트워크가 닿는 유일한 함수 - 테스트는
    `parse_feed`/`select_relevant`를 직접 호출해 이 함수를 우회한다."""
    async with httpx.AsyncClient(timeout=FEED_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(source.feed_url)
        response.raise_for_status()
        if len(response.content) > MAX_FEED_BYTES:
            raise ValueError(f"RSS 응답이 너무 큽니다({len(response.content)} bytes) - 수집을 중단합니다.")
        xml_text = response.text
    articles = parse_feed(xml_text, source=source.code, source_name=source.name)
    return select_relevant(articles, source)
