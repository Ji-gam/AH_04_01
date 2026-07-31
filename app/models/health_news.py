from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HealthNews(Base):
    """T-LLM-6: 외부 언론사에서 수집한 건강 뉴스 기사 한 건.

    기존 `health_contents`(T-LLM-3)와 정체성이 다르다 - 그쪽은 "LLM이 매일 새로 지어내는 글"이라
    (disease_code, category, content_date) 복합 유니크로 하루 한 건만 허용하지만, 여기는 "URL로
    식별되는 실제 기사"이므로 하루에 몇 건이 들어와도 상관없고 유니크 기준도 원문 URL이다.
    (재활용 검토 결과는 docs/tasks/T-LLM-6-health-news-feed.md 4절 참고.)
    """

    __tablename__ = "health_news"
    # 같은 RSS를 여러 번 수집해도 기사가 중복으로 쌓이지 않게 하는 유일한 열쇠.
    # source를 함께 묶는 이유: 다른 매체가 같은 URL을 쓸 일은 없지만, 소스별로 URL 규칙이
    # 달라질 수 있어 소스 축을 남겨두는 편이 나중에 파서를 늘릴 때 안전하다.
    __table_args__ = (UniqueConstraint("source", "source_url", name="uq_health_news_source_url"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 수집기(파서)를 고르는 키. "KORMEDI" 등 대문자 코드.
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # 화면에 그대로 노출할 매체명("코메디닷컴"). source 코드와 표시명을 분리해 두면
    # 표기가 바뀌어도 수집 코드를 건드리지 않는다.
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # 기사 발행일. 피드 정렬 기준은 수집 시각이 아니라 이것이다(수집이 밀려도 순서가 안 뒤집힌다).
    # index=True가 만드는 이름(ix_health_news_published_at)이 마이그레이션 0059의 인덱스명과 같다.
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    # 본문 평문. 단락은 빈 줄("\n\n")로 구분한다.
    #
    # RSS의 content:encoded는 HTML이지만 **HTML을 그대로 저장하지 않는다** - 외부 사이트가 준
    # HTML을 프론트에서 dangerouslySetInnerHTML로 그리면 그 사이트가 우리 앱에 스크립트를
    # 심을 수 있는 통로가 된다(제3자 HTML 주입). 수집 시점에 평문으로 뽑아 두면 프론트는
    # 단락을 <p>로만 그리면 되고 주입 통로가 아예 생기지 않는다.
    # 대신 굵은 글씨/본문 중간 링크는 버린다 - 뉴스 읽기에는 손실이 크지 않다고 판단했다.
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 대표 이미지 - 원본 서버 URL을 그대로 참조한다(우리 디스크에 복사하지 않음). 없는 기사도 있다.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 기사의 사진 설명(<figcaption>). 출처 표기가 여기 들어있어 같이 보여줘야 한다.
    image_caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 개인화(2단계)에서 LLM이 채운다. 수집 시점에는 아직 분류하지 않으므로 NULL.
    disease_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # RSS <category> 목록(예: ["건강","아토피","알레르기"]). 지금은 화면에 쓰지 않지만
    # 2단계 질환 태깅의 핵심 힌트라서 수집 때 같이 저장한다 - 지금 버리면 피드에서 밀려난
    # 기사는 다시 못 받으므로 되돌릴 수 없다.
    source_categories: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    # 카드뉴스 슬라이드 배열({"slides": [...]}). 수집 배치에서 미리 채워 사용자 대기를 0으로 만든다.
    # 기사 1건 : 요약 1개(1:1)라서 별도 테이블로 빼지 않았다.
    #
    # `none_as_null=True`가 꼭 필요하다. 기본 `JSON`은 Python `None`을 SQL NULL이 아니라
    # **JSON 문자열 `'null'`로 저장**하는데, 읽을 때는 다시 Python `None`으로 돌려준다.
    # 그러면 파이썬 검사와 SQL 검사가 서로 다른 답을 낸다:
    #   `news.card_summary is None`      → True  (화면: "요약 없음")
    #   `card_summary IS NULL`           → False (배치: 대상이 아님)
    # 그렇게 쓰인 행은 **영구히 갇힌다** - 화면엔 계속 요약 없음인데 어떤 배치도 채워주지 않는다.
    # (2026-07-31 발견. `save()`가 이 컬럼을 안 넘겨서 운영 데이터는 무사했지만, 명시적으로
    #  None을 쓰는 코드 한 줄이면 재현된다 - 실제로 테스트와 진단 스크립트에서 두 번 겪었다.)
    # 컬럼 타입이 바뀌는 게 아니라 직렬화 방식만 정하는 설정이라 마이그레이션은 필요 없다.
    card_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
