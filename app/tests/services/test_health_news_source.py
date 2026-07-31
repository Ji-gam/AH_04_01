"""T-LLM-6 수집기 테스트. 네트워크를 타지 않는다 - 순수 함수(`parse_feed` / `select_relevant` /
`take_latest` / `extract_*`)에 문자열을 직접 넣어 `fetch`(유일하게 네트워크를 쓰는 함수)를 우회한다.

XML/HTML 조각은 모두 실제 응답의 구조를 축약한 것이다:
  - 피드 조각: 2026-07-30 코메디닷컴(WordPress content:encoded, figure/img/figcaption,
    WordPress가 붙이는 "appeared first on" 홍보 단락)
  - 기사 페이지 조각: 2026-07-31 헬스경향/코리아헬스로그(schema.org itemprop="articleBody",
    기사 끝의 AI 생성 FAQ 블록, 저작권 문구, 상대경로 이미지)
"""

from datetime import datetime

import pytest

from app.services.health_news_source import (
    KHEALTH,
    KORMEDI,
    MAX_ARTICLES_PER_SOURCE,
    BodyLocation,
    FeedEntry,
    extract_article_page_content,
    extract_feed_content,
    parse_feed,
    select_relevant,
    take_latest,
)

_FEED_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>코메디닷컴</title>
    {items}
  </channel>
</rss>
"""

_FULL_ITEM = """
    <item>
      <title>&#8216;체감 기준&#8217; 못 미쳐</title>
      <link>https://kormedi.com/2839968/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
      <category>건강</category>
      <category>아토피</category>
      <content:encoded><![CDATA[
        <figure class="wp-block-image"><img decoding="async" width="724"
          src="https://cdn.kormedi.com/wp-content/uploads/2026/07/photo.jpg" alt=""/>
          <figcaption class="wp-element-caption">사진=게티이미지뱅크</figcaption></figure>
        <p>첫 번째 단락이다.</p>
        <p><strong>굵은</strong> 글씨가 섞인 두 번째 단락이다.</p>
        <p></p>
        <p>The post <a href="https://kormedi.com/2839968/">기사</a> appeared first on 코메디닷컴.</p>
      ]]></content:encoded>
    </item>
"""

# CMS 계열 매체(헬스경향 등)의 피드 item. content:encoded가 아예 없고 description은 299자
# 요약뿐이며, pubDate가 RSS 표준이 아니라 타임존 없는 한국 시각이다.
_SUMMARY_ONLY_ITEM = """
    <item>
      <title>일회용 안약, 한 번 쓰고 버려야 합니다</title>
      <link>https://www.k-health.com/news/articleView.html?idxno=100414</link>
      <pubDate>2026-07-31 17:15:31</pubDate>
      <description>최근 고령화와 건강검진 활성화로 녹내장 환자가 늘면서...</description>
    </item>
"""

# 실제 기사 페이지 구조. 확인해야 할 함정이 셋 들어있다:
#   1) 페이지 상단 자바스크립트에 id="article-view-content-div"가 먼저 등장한다(앵커로 쓰면 안 됨)
#   2) 본문 뒤에 AI가 생성한 FAQ 문답 블록이 붙는다
#   3) 이미지가 상대경로다
_ARTICLE_PAGE = """<!DOCTYPE html>
<html><head><meta property="og:image" content="https://cdn.k-health.com/og.jpg"/></head>
<body>
<script>$('#article-view-content-div').on('copy', function(e){ /* 출처 붙이는 코드 */ });</script>
<article id="article-view-content-div" itemprop="articleBody">
  <figure class="photo-layout"><img src="/news/photo/202607/100414_200581_1424.png" width="960"/>
    <figcaption class="text-left">일회용 안약은 한 번만 사용할 때 가장 안전하다.</figcaption></figure>
  <p>보존제가 없는 일회용 안약 처방이 확대되고 있다.</p>
  <p><strong>■보관법도 중요하다</strong></p>
  <p>제품마다 냉장 보관이 필요한 경우와 실온 보관이 다르다.</p>
  <div id="tem-type-8">
    <p><strong>FAQ</strong></p>
    <p>Q: 일회용 안약을 재사용해도 되나?<br/>A: 안 된다.</p>
  </div>
</article>
<div class="view-copyright"><p>저작권자 &copy; 헬스경향 무단전재 및 재배포 금지</p></div>
<div class="related"><p>관련기사: 녹내장 환자 급증</p></div>
</body></html>
"""


def _build_feed(*items: str) -> str:
    return _FEED_TEMPLATE.format(items="".join(items))


def _parse(*items: str) -> list[FeedEntry]:
    return parse_feed(_build_feed(*items))


# ── 피드 파싱 ────────────────────────────────────────────────────────────────


def test_parses_entry_fields_from_feed_item() -> None:
    (entry,) = _parse(_FULL_ITEM)

    assert entry.source_url == "https://kormedi.com/2839968/"
    # HTML 엔티티(&#8216;)가 실제 따옴표로 복원되어야 한다.
    assert entry.title == "‘체감 기준’ 못 미쳐"
    assert entry.source_categories == ["건강", "아토피"]


def test_published_at_is_naive_utc() -> None:
    """DB 컬럼이 timezone 없는 DATETIME이므로 tzinfo를 떼서 UTC 시각으로 저장한다."""
    (entry,) = _parse(_FULL_ITEM)

    assert entry.published_at.tzinfo is None
    assert entry.published_at.isoformat() == "2026-07-30T07:21:04"


def test_cms_style_local_datetime_is_converted_to_utc() -> None:
    """CMS 계열 매체는 pubDate를 `2026-07-31 17:15:31`처럼 **타임존 없는 한국 시각**으로 준다
    (2026-07-31 실측). 두 가지가 걸려 있다:

    1. RFC 2822가 아니라서 표준 파서가 실패한다 - 그대로 두면 그 매체 기사가 **전부** 버려진다.
    2. 한국 시각을 그대로 저장하면 UTC로 저장되는 코메디 기사보다 9시간 미래가 되어, 피드
       맨 위를 늘 이 매체가 차지한다.
    """
    (entry,) = _parse(_SUMMARY_ONLY_ITEM)

    assert entry.published_at.tzinfo is None
    # 17:15:31 KST == 08:15:31 UTC
    assert entry.published_at.isoformat() == "2026-07-31T08:15:31"


def test_rfc_date_with_offset_is_shifted_to_utc() -> None:
    """타임존이 붙어 오면 그 타임존대로 UTC로 옮긴다 - tzinfo만 떼면 9시간이 틀어진다."""
    item = """
    <item>
      <title>제목</title>
      <link>https://example.test/tz/</link>
      <pubDate>Fri, 31 Jul 2026 17:15:31 +0900</pubDate>
    </item>
    """
    (entry,) = _parse(item)

    assert entry.published_at.isoformat() == "2026-07-31T08:15:31"


def test_title_bom_is_removed() -> None:
    """제목 앞에 BOM을 붙여 보내는 매체가 있다(정신의학신문 실측). 화면에서는 빈 칸처럼 보이고
    음성읽기에서는 잡음이 되므로 수집 시점에 떼어낸다."""
    item = """
    <item>
      <title>﻿성인 ADHD, 일상에서 나타나는 증상</title>
      <link>https://www.psychiatricnews.net/1/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
    </item>
    """
    (entry,) = _parse(item)

    assert entry.title == "성인 ADHD, 일상에서 나타나는 증상"


def test_entry_without_encoded_body_is_kept() -> None:
    """CMS 계열 매체는 피드에 본문을 주지 않는다 - 그렇다고 버리면 안 된다. 본문은 나중에
    기사 페이지에서 채운다."""
    (entry,) = _parse(_SUMMARY_ONLY_ITEM)

    assert entry.encoded_html == ""
    assert entry.source_url.endswith("idxno=100414")


@pytest.mark.parametrize(
    "broken_item",
    [
        # link 없음
        "<item><title>제목</title><pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate></item>",
        # pubDate 없음
        "<item><title>제목</title><link>https://kormedi.com/2/</link></item>",
        # pubDate 형식이 깨짐
        "<item><title>제목</title><link>https://kormedi.com/3/</link><pubDate>어제</pubDate></item>",
        # title 없음
        "<item><link>https://kormedi.com/4/</link><pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate></item>",
    ],
)
def test_skips_broken_item_but_keeps_healthy_ones(broken_item: str) -> None:
    """기사 한 건이 깨져도 나머지는 살려야 한다 - 한 건 때문에 수집 전체가 빈손이 되면 손해가 크다."""
    entries = _parse(broken_item, _FULL_ITEM)

    assert len(entries) == 1
    assert entries[0].source_url == "https://kormedi.com/2839968/"


def test_truncates_title_to_column_limit() -> None:
    """제목이 컬럼 길이(300)를 넘으면 잘라서 저장한다 - 기사 한 건 때문에 수집이 실패하는 것보다 낫다."""
    item = f"""
    <item>
      <title>{"가" * 400}</title>
      <link>https://kormedi.com/6/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
    </item>
    """
    (entry,) = _parse(item)

    assert len(entry.title) == 300


def test_rejects_feed_with_doctype_declaration() -> None:
    """엔티티 폭탄(billion laughs) 방어. 정상 RSS에는 DOCTYPE이 없으므로 보이면 파싱 자체를 거절한다."""
    hostile = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE rss [<!ENTITY a "aaaaaaaaaa">]>\n'
        '<rss version="2.0"><channel><title>&a;</title></channel></rss>'
    )

    with pytest.raises(ValueError, match="DOCTYPE"):
        parse_feed(hostile)


# ── 피드에서 본문 뽑기 (코메디닷컴) ──────────────────────────────────────────


def test_feed_body_is_plain_paragraphs_without_html() -> None:
    """본문은 평문이어야 한다 - HTML을 그대로 저장하면 외부 사이트가 우리 앱에 스크립트를
    심는 통로가 되므로(제3자 HTML 주입), 수집 시점에 태그를 제거한다."""
    (entry,) = _parse(_FULL_ITEM)

    content = extract_feed_content(entry)

    assert content is not None
    assert "<" not in content.body_text
    assert content.body_text == "첫 번째 단락이다.\n\n굵은 글씨가 섞인 두 번째 단락이다."


def test_feed_body_drops_wordpress_promo_paragraph() -> None:
    """WordPress가 자동으로 붙이는 "appeared first on" 홍보 단락은 본문이 아니므로 버린다
    (카드요약 품질을 떨어뜨린다)."""
    (entry,) = _parse(_FULL_ITEM)

    content = extract_feed_content(entry)

    assert content is not None
    assert "appeared first on" not in content.body_text


def test_feed_content_extracts_first_image_and_caption() -> None:
    (entry,) = _parse(_FULL_ITEM)

    content = extract_feed_content(entry)

    assert content is not None
    assert content.image_url == "https://cdn.kormedi.com/wp-content/uploads/2026/07/photo.jpg"
    assert content.image_caption == "사진=게티이미지뱅크"


def test_feed_content_without_image_yields_none_fields() -> None:
    item = """
    <item>
      <title>사진 없는 기사</title>
      <link>https://kormedi.com/1/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
      <content:encoded><![CDATA[<p>본문만 있다.</p>]]></content:encoded>
    </item>
    """
    (entry,) = _parse(item)

    content = extract_feed_content(entry)

    assert content is not None
    assert content.image_url is None
    assert content.image_caption is None
    assert content.body_text == "본문만 있다."


@pytest.mark.parametrize(
    "encoded",
    [
        "",  # content:encoded가 아예 없다
        '<figure><img src="https://x/y.jpg"/></figure>',  # 사진만 있고 본문 단락이 없다
    ],
)
def test_feed_content_is_none_when_there_is_no_body(encoded: str) -> None:
    """본문 없는 기사는 저장하지 않는다 - 읽을 것도 없고 카드요약 재료도 없다."""
    entry = FeedEntry(
        source_url="https://kormedi.com/9/",
        title="제목",
        published_at=datetime(2026, 7, 30, 7, 0, 0),
        source_categories=[],
        encoded_html=encoded,
    )

    assert extract_feed_content(entry) is None


# ── 기사 페이지에서 본문 뽑기 (CMS 계열 매체) ────────────────────────────────

_ARTICLE_URL = "https://www.k-health.com/news/articleView.html?idxno=100414"


def test_article_page_body_is_extracted_as_plain_paragraphs() -> None:
    content = extract_article_page_content(_ARTICLE_PAGE, _ARTICLE_URL)

    assert content is not None
    assert content.body_text == (
        "보존제가 없는 일회용 안약 처방이 확대되고 있다.\n\n"
        "■보관법도 중요하다\n\n"
        "제품마다 냉장 보관이 필요한 경우와 실온 보관이 다르다."
    )


def test_article_page_drops_ai_generated_faq_block() -> None:
    """기사 끝에 붙는 AI 생성 Q&A는 기사 내용을 되풀이한다. 남겨두면 카드요약이 같은 말을
    재료로 쓰고, [음성으로 듣기]가 같은 이야기를 두 번 읽는다."""
    content = extract_article_page_content(_ARTICLE_PAGE, _ARTICLE_URL)

    assert content is not None
    assert "FAQ" not in content.body_text
    assert "Q: " not in content.body_text


def test_article_page_drops_copyright_and_related_articles() -> None:
    content = extract_article_page_content(_ARTICLE_PAGE, _ARTICLE_URL)

    assert content is not None
    assert "저작권자" not in content.body_text
    assert "관련기사" not in content.body_text


def test_article_page_image_becomes_absolute_url() -> None:
    """어떤 매체는 이미지를 `/news/photo/...` 상대경로로 준다. 그대로 저장하면 우리 도메인
    기준으로 해석돼 사진이 깨진다."""
    content = extract_article_page_content(_ARTICLE_PAGE, _ARTICLE_URL)

    assert content is not None
    assert content.image_url == "https://www.k-health.com/news/photo/202607/100414_200581_1424.png"
    assert content.image_caption == "일회용 안약은 한 번만 사용할 때 가장 안전하다."


def test_article_page_without_body_anchor_yields_none() -> None:
    """상대 매체가 템플릿을 바꾸면 여기서 None이 나온다 - 수집 결과의 `unreadable` 숫자가
    올라가서 관리자가 알아챌 수 있다(조용히 빈 기사를 저장하지 않는다)."""
    assert extract_article_page_content("<html><body><p>본문 아님</p></body></html>", _ARTICLE_URL) is None


def test_article_page_body_survives_the_javascript_decoy() -> None:
    """페이지 상단 자바스크립트에 id="article-view-content-div"가 먼저 나온다. 그걸 앵커로
    쓰면 본문을 놓치므로 itemprop="articleBody"를 기준으로 삼는다."""
    content = extract_article_page_content(_ARTICLE_PAGE, _ARTICLE_URL)

    assert content is not None
    assert "출처 붙이는 코드" not in content.body_text


# ── 걸러내기 ─────────────────────────────────────────────────────────────────


def _entry(*categories: str, published_at: datetime | None = None) -> FeedEntry:
    return FeedEntry(
        source_url=f"https://kormedi.com/{'-'.join(categories) or 'none'}/",
        title="제목",
        published_at=published_at or datetime(2026, 7, 30, 7, 0, 0),
        source_categories=list(categories),
        encoded_html="<p>본문</p>",
    )


def test_excludes_stock_disclosure_and_pharma_articles() -> None:
    """코메디 피드에는 상장사 공시("일동제약 2분기 영업이익")와 제약사 파이프라인 기사가
    섞여 온다. 둘 다 투자자용이라 건강정보 피드에 뜨면 안 된다(2026-07-30 실측)."""
    entries = [
        _entry("건강", "아토피"),
        _entry("AI 공시뉴스"),
        _entry("바이오·제약", "바이오워치"),
    ]

    result = select_relevant(entries, KORMEDI)

    assert result.excluded == 2
    assert [e.source_categories for e in result.entries] == [["건강", "아토피"]]


def test_keeps_celebrity_health_articles() -> None:
    """셀럽헬스는 남긴다 - 다이어트/식단 같은 실제 생활 팁이 담기는 경우가 있어서
    (2026-07-30 결정). 필터가 과하게 걷어내지 않는지 고정해둔다."""
    result = select_relevant([_entry("건강", "기획ㆍ연재-셀럽헬스", "다이어트")], KORMEDI)

    assert result.excluded == 0
    assert len(result.entries) == 1


def test_entry_without_categories_is_kept() -> None:
    """카테고리가 아예 없는 기사는 판단 근거가 없으므로 버리지 않는다. CMS 계열 매체는
    카테고리를 아예 주지 않으므로 이 동작이 곧 그 매체들의 기본 동작이다."""
    result = select_relevant([_entry()], KHEALTH)

    assert result.excluded == 0
    assert len(result.entries) == 1


# ── 매체당 상한 ──────────────────────────────────────────────────────────────


def test_take_latest_keeps_the_newest_and_counts_the_rest() -> None:
    """상한을 넘긴 기사는 버린 게 아니라 미룬 것이다 - 다음 수집에서 다시 후보가 된다.
    그래서 숫자로 보고한다(조용히 사라지면 파싱 실패와 구분이 안 된다)."""
    entries = [_entry(f"c{day}", published_at=datetime(2026, 7, day, 9, 0, 0)) for day in range(1, 9)]

    kept, over_limit = take_latest(entries, limit=3)

    assert [e.published_at.day for e in kept] == [8, 7, 6]
    assert over_limit == 5


def test_take_latest_sorts_even_when_the_feed_is_out_of_order() -> None:
    """피드가 최신순으로 온다고 믿지 않는다 - 순서가 뒤집힌 피드에서 앞에서부터 잘라내면
    옛 기사만 골라오게 된다."""
    entries = [
        _entry("old", published_at=datetime(2026, 7, 1, 9, 0, 0)),
        _entry("new", published_at=datetime(2026, 7, 31, 9, 0, 0)),
    ]

    kept, over_limit = take_latest(entries, limit=1)

    assert kept[0].source_categories == ["new"]
    assert over_limit == 1


def test_take_latest_reports_nothing_deferred_when_under_the_limit() -> None:
    kept, over_limit = take_latest([_entry("only")], limit=MAX_ARTICLES_PER_SOURCE)

    assert len(kept) == 1
    assert over_limit == 0


# ── 소스 정의 ────────────────────────────────────────────────────────────────


def test_new_sources_read_the_article_page_and_kormedi_does_not() -> None:
    """소스가 늘어도 수집 서비스는 매체를 모른다 - 본문을 어디서 얻는지는 이 값 하나로만
    갈린다. 새 매체를 잘못 FEED로 두면 피드에 본문이 없어 전부 unreadable이 된다."""
    assert KORMEDI.body_location is BodyLocation.FEED
    assert KHEALTH.body_location is BodyLocation.ARTICLE_PAGE
