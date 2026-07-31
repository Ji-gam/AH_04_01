"""T-LLM-6 RSS 파서 테스트. 네트워크를 타지 않는다 - `parse_feed`에 XML 문자열을 직접 넣어
`fetch_kormedi`(유일하게 네트워크를 쓰는 함수)를 우회한다.

XML 조각은 2026-07-30 코메디닷컴 실제 피드의 구조(WordPress content:encoded, figure/img/
figcaption, WordPress가 붙이는 "appeared first on" 홍보 단락)를 그대로 축약한 것이다.
"""

from datetime import datetime

import pytest

from app.services.health_news_source import KORMEDI, ParsedArticle, parse_feed, select_relevant

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


def _build_feed(*items: str) -> str:
    return _FEED_TEMPLATE.format(items="".join(items))


def _parse(*items: str):  # noqa: ANN202
    return parse_feed(_build_feed(*items), source="KORMEDI", source_name="코메디닷컴")


def test_parses_article_fields_from_feed_item() -> None:
    (article,) = _parse(_FULL_ITEM)

    assert article.source == "KORMEDI"
    assert article.source_name == "코메디닷컴"
    assert article.source_url == "https://kormedi.com/2839968/"
    # HTML 엔티티(&#8216;)가 실제 따옴표로 복원되어야 한다.
    assert article.title == "‘체감 기준’ 못 미쳐"
    assert article.source_categories == ["건강", "아토피"]


def test_published_at_is_naive_utc() -> None:
    """DB 컬럼이 timezone 없는 DATETIME이므로 tzinfo를 떼서 UTC 시각으로 저장한다."""
    (article,) = _parse(_FULL_ITEM)

    assert article.published_at.tzinfo is None
    assert article.published_at.isoformat() == "2026-07-30T07:21:04"


def test_body_text_is_plain_paragraphs_without_html() -> None:
    """본문은 평문이어야 한다 - HTML을 그대로 저장하면 외부 사이트가 우리 앱에 스크립트를
    심는 통로가 되므로(제3자 HTML 주입), 수집 시점에 태그를 제거한다."""
    (article,) = _parse(_FULL_ITEM)

    assert "<" not in article.body_text
    assert article.body_text == "첫 번째 단락이다.\n\n굵은 글씨가 섞인 두 번째 단락이다."


def test_body_text_drops_wordpress_promo_paragraph() -> None:
    """WordPress가 자동으로 붙이는 "appeared first on" 홍보 단락은 본문이 아니므로 버린다
    (카드요약 품질을 떨어뜨린다)."""
    (article,) = _parse(_FULL_ITEM)

    assert "appeared first on" not in article.body_text


def test_extracts_first_image_and_caption() -> None:
    (article,) = _parse(_FULL_ITEM)

    assert article.image_url == "https://cdn.kormedi.com/wp-content/uploads/2026/07/photo.jpg"
    assert article.image_caption == "사진=게티이미지뱅크"


def test_article_without_image_yields_none() -> None:
    item = """
    <item>
      <title>사진 없는 기사</title>
      <link>https://kormedi.com/1/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
      <content:encoded><![CDATA[<p>본문만 있다.</p>]]></content:encoded>
    </item>
    """
    (article,) = _parse(item)

    assert article.image_url is None
    assert article.image_caption is None
    assert article.body_text == "본문만 있다."


@pytest.mark.parametrize(
    "broken_item",
    [
        # link 없음
        """<item><title>제목</title><pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
           <content:encoded><![CDATA[<p>본문</p>]]></content:encoded></item>""",
        # pubDate 없음
        """<item><title>제목</title><link>https://kormedi.com/2/</link>
           <content:encoded><![CDATA[<p>본문</p>]]></content:encoded></item>""",
        # pubDate 형식이 깨짐
        """<item><title>제목</title><link>https://kormedi.com/3/</link><pubDate>어제</pubDate>
           <content:encoded><![CDATA[<p>본문</p>]]></content:encoded></item>""",
        # content:encoded 없음
        """<item><title>제목</title><link>https://kormedi.com/4/</link>
           <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate></item>""",
        # 본문 단락이 없어 평문이 비는 경우
        """<item><title>제목</title><link>https://kormedi.com/5/</link>
           <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
           <content:encoded><![CDATA[<figure><img src="https://x/y.jpg"/></figure>]]></content:encoded></item>""",
    ],
)
def test_skips_broken_item_but_keeps_healthy_ones(broken_item: str) -> None:
    """기사 한 건이 깨져도 나머지는 살려야 한다 - 한 건 때문에 수집 전체가 빈손이 되면 손해가 크다."""
    articles = _parse(broken_item, _FULL_ITEM)

    assert len(articles) == 1
    assert articles[0].source_url == "https://kormedi.com/2839968/"


def test_truncates_title_to_column_limit() -> None:
    """제목이 컬럼 길이(300)를 넘으면 잘라서 저장한다 - 기사 한 건 때문에 수집이 실패하는 것보다 낫다."""
    long_title = "가" * 400
    item = f"""
    <item>
      <title>{long_title}</title>
      <link>https://kormedi.com/6/</link>
      <pubDate>Thu, 30 Jul 2026 07:21:04 +0000</pubDate>
      <content:encoded><![CDATA[<p>본문</p>]]></content:encoded>
    </item>
    """
    (article,) = _parse(item)

    assert len(article.title) == 300


def test_rejects_feed_with_doctype_declaration() -> None:
    """엔티티 폭탄(billion laughs) 방어. 정상 RSS에는 DOCTYPE이 없으므로 보이면 파싱 자체를 거절한다."""
    hostile = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE rss [<!ENTITY a "aaaaaaaaaa">]>\n'
        '<rss version="2.0"><channel><title>&a;</title></channel></rss>'
    )

    with pytest.raises(ValueError, match="DOCTYPE"):
        parse_feed(hostile, source="KORMEDI", source_name="코메디닷컴")


def _article(*categories: str) -> ParsedArticle:
    return ParsedArticle(
        source="KORMEDI",
        source_name="코메디닷컴",
        source_url=f"https://kormedi.com/{'-'.join(categories) or 'none'}/",
        title="제목",
        published_at=datetime(2026, 7, 30, 7, 0, 0),
        body_text="본문",
        image_url=None,
        image_caption=None,
        source_categories=list(categories),
    )


def test_excludes_stock_disclosure_and_pharma_articles() -> None:
    """코메디 피드에는 상장사 공시("일동제약 2분기 영업이익")와 제약사 파이프라인 기사가
    섞여 온다. 둘 다 투자자용이라 건강정보 피드에 뜨면 안 된다(2026-07-30 실측)."""
    articles = [
        _article("건강", "아토피"),
        _article("AI 공시뉴스"),
        _article("바이오·제약", "바이오워치"),
    ]

    result = select_relevant(articles, KORMEDI)

    assert result.excluded == 2
    assert [a.source_categories for a in result.articles] == [["건강", "아토피"]]


def test_keeps_celebrity_health_articles() -> None:
    """셀럽헬스는 남긴다 - 다이어트/식단 같은 실제 생활 팁이 담기는 경우가 있어서
    (2026-07-30 결정). 필터가 과하게 걷어내지 않는지 고정해둔다."""
    articles = [_article("건강", "기획ㆍ연재-셀럽헬스", "다이어트")]

    result = select_relevant(articles, KORMEDI)

    assert result.excluded == 0
    assert len(result.articles) == 1


def test_article_without_categories_is_kept() -> None:
    """카테고리가 아예 없는 기사는 판단 근거가 없으므로 버리지 않는다."""
    result = select_relevant([_article()], KORMEDI)

    assert result.excluded == 0
    assert len(result.articles) == 1
