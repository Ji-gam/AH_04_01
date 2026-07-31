"""T-LLM-6 카드뉴스 요약 스키마.

**역할 분담이 이 파일의 핵심이다.**

- LLM이 정하는 것: 글자와 숫자뿐(`tag`/`stat`/`substat`/`text`)과 아이콘 **선택**(`icon_key`)
- 코드가 정하는 것: 배경 그라데이션, 아이콘 배치, 워터마크, 여백, 글자 크기 — 전부

그래서 LLM이 최악의 답을 줘도 카드가 못생겨질 수는 없다. 표지 카드와 마지막 면책 카드도
LLM이 만들지 않는다 - 템플릿이 기사 제목과 고정 문구로 직접 그린다(면책 문구가 LLM 손에
달려 있으면 안 된다, REQ-INFO-004).

아이콘을 자유 서술로 받지 않고 `Literal` 객관식으로 받는 이유: LLM에게 "어울리는 아이콘을
알려줘"라고 물으면 우리가 갖고 있지도 않은 이름을 답한다. 선택지를 못 박으면 답이 그대로
프론트의 아이콘 컴포넌트 키가 되어, 중간에 해석하는 단계(=두 번째 LLM)가 필요 없다.
"""

from datetime import datetime
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, Field, field_validator

# 프로토타입 2종(당뇨/심장)에서 실측한 최대 길이에 약간의 헤드룸을 준 값.
# tag 6 / stat 10 / substat 14 / text 50 이 실측치였다(docs/dev/sample_card_news/).
TAG_MAX = 8
STAT_MAX = 12
SUBSTAT_MAX = 18
# (2026-07-31) 60 → 110으로 올렸다. 카드 폭 315px / 폰트 14px에서 한 줄이 약 20자라 60자면
# 2줄밖에 안 나왔는데, 실측해보니 카드에 292px(약 15줄)가 비어 있었다. 사용자가 기사 원문을
# 끝까지 읽지 않는다는 전제에서 카드가 내용을 담아야 하므로 3~5줄(60~110자)을 목표로 한다.
TEXT_MAX = 110
# 프로토타입은 본문 카드 4장이었다. 표지/면책은 템플릿이 따로 붙이므로 여기 개수에 안 들어간다.
SLIDES_MIN = 3
SLIDES_MAX = 5

# 선택지는 프론트에 설치된 lucide-react 1.27.0에 **실제로 존재하는 이름만** 넣었다
# (전수 확인 2026-07-30). 파일명이 kebab-case라 이 값이 그대로 아이콘 파일 이름과 같다.
# 코메디 기사가 다루는 축(수면/운동/식이/검사수치/약/주의/심리)을 덮도록 골랐다.
IconKey = Literal[
    # 수면·시간
    "moon",
    "bed",
    "timer",
    "clock",
    "calendar-check",
    # 운동·활동
    "dumbbell",
    "footprints",
    "activity",
    "heart-pulse",
    "trending-up",
    # 신체·장기
    "heart",
    "brain",
    "bone",
    "eye",
    "stethoscope",
    # 식이·음식
    "apple",
    "carrot",
    "salad",
    "egg",
    "fish",
    "wheat",
    "milk",
    "coffee",
    "droplet",
    "utensils",
    # 금지·주의
    "ban",
    "cigarette-off",
    "wine",
    "triangle-alert",
    "shield-alert",
    # 약·치료
    "pill",
    "syringe",
    "thermometer",
    "hospital",
    # 검사·수치
    "flask-conical",
    "microscope",
    "test-tube",
    "gauge",
    "chart-line",
    # 문서·기록
    "clipboard-list",
    "scroll-text",
    "book-open",
    # 안전·확인
    "shield-check",
    "circle-check",
    "info",
    # 심리·사람
    "smile",
    "frown",
    "cloud-rain",
    "users",
    "scale",
    # 강조
    "sparkles",
    "lightbulb",
]

# Literal이 유일한 원본이고 이 튜플은 거기서 뽑는다 - 두 곳을 따로 관리하면 반드시 어긋난다.
ICON_KEYS: tuple[str, ...] = get_args(IconKey)

# LLM이 목록에 없는 아이콘을 답했을 때 쓸 값. 카드 하나를 못 그리는 것보다 중립 아이콘이 낫다.
FALLBACK_ICON_KEY = "info"


def _clip(value: object, limit: int) -> object:
    """길이를 넘으면 잘라낸다. **거절하지 않는 게 핵심** - ai_worker는 함수호출 방식으로
    생성하므로 스키마의 maxLength가 LLM에게 강제되지 않고 권고로만 전달된다. 몇 글자 넘겼다고
    검증 예외를 던지면 카드요약 전체를 잃는다."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip()
    return value


def _clip_at_sentence(value: object, limit: int) -> object:
    """`_clip`과 같지만 **문장이 끝나는 자리에서** 자른다.

    (2026-07-31) 설명문을 3~5줄로 늘린 뒤 실측했더니 24장 중 4장이 문장 중간에서 잘렸다
    ("이는 치료 지연의 위험을 내포", "큰 도움이 되지 않는"). LLM이 목표 길이를 조금씩 넘겨
    쓰는 건 프롬프트로 완전히 막을 수 없으니, 잘리더라도 문장으로 끝나게 구조로 보장한다.

    문장 끝을 너무 앞에서 찾으면(예: 첫 문장이 20자) 내용이 크게 잘리므로, 한계의 절반보다
    뒤에 있을 때만 그 자리를 쓴다. 그 외에는 기존처럼 그냥 자른다.
    """
    if not isinstance(value, str) or len(value) <= limit:
        return value
    head = value[:limit]
    end = max(head.rfind("."), head.rfind("!"), head.rfind("?"))
    if end >= limit // 2:
        return head[: end + 1]
    return head.rstrip()


def _blank_to_none(value: object) -> object:
    """빈 문자열/공백만 있는 값을 None으로 바꾼다. LLM은 "값이 없음"을 None이 아니라 ""로
    답하는 경우가 있어서(실측: 31장 중 3장), 그대로 두면 화면에 빈칸이 그려진다."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class CardSlide(BaseModel):
    """카드 한 장의 내용. 프로토타입의 카드 구조와 1:1로 대응한다.

    stat(큰 숫자)과 substat(그 숫자의 부연)을 나눠 받는 이유: 하나로 합쳐 받으면 "10~30분 내 /
    15~30분 걷기"처럼 길어져 줄바꿈이 4줄까지 터지고 아이콘을 화면 밖으로 밀어낸다
    (프로토타입에서 실제로 겪은 사고).

    `stat`이 없는 카드도 정식으로 허용한다. 기사에 마땅한 숫자가 없는 카드(예: "혼자 감정을
    억누르기보다 주변과 나누는 것이 회복에 도움")를 억지로 숫자로 만들라고 강요하면 LLM이
    **없는 숫자를 지어낸다** - 건강 정보에서는 빈칸보다 나쁜 결과다. 대신 템플릿이 stat 없는
    카드를 "큰 글씨 문장 카드"로 그린다.
    """

    icon_key: IconKey
    tag: Annotated[str, Field(max_length=TAG_MAX, description="카드 주제 라벨. 예: 수면, 근력운동")]
    stat: Annotated[
        str | None,
        Field(default=None, max_length=STAT_MAX, description="가장 큰 글씨로 보여줄 핵심 숫자. 예: +1시간, 80%+"),
    ] = None
    substat: Annotated[
        str | None,
        Field(default=None, max_length=SUBSTAT_MAX, description="stat을 한 조각 보충하는 짧은 말. 없으면 비워둔다"),
    ] = None
    text: Annotated[str, Field(max_length=TEXT_MAX, description="카드 설명 한 문장. 쉬운 말로")]

    @field_validator("icon_key", mode="before")
    @classmethod
    def coerce_unknown_icon(cls, value: object) -> object:
        return value if value in ICON_KEYS else FALLBACK_ICON_KEY

    @field_validator("tag", mode="before")
    @classmethod
    def clip_tag(cls, value: object) -> object:
        return _clip(value, TAG_MAX)

    @field_validator("stat", mode="before")
    @classmethod
    def clip_stat(cls, value: object) -> object:
        return _clip(_blank_to_none(value), STAT_MAX)

    @field_validator("substat", mode="before")
    @classmethod
    def clip_substat(cls, value: object) -> object:
        return _clip(_blank_to_none(value), SUBSTAT_MAX)

    @field_validator("text", mode="before")
    @classmethod
    def clip_text(cls, value: object) -> object:
        # 설명문만 문장 단위로 자른다. tag/stat/substat은 문장이 아니라 짧은 라벨이라 해당 없음.
        return _clip_at_sentence(value, TEXT_MAX)


class CardSummary(BaseModel):
    """기사 한 건의 카드뉴스 요약. `health_news.card_summary` JSON 컬럼에 이 모양으로 저장된다."""

    slides: Annotated[
        list[CardSlide],
        Field(min_length=SLIDES_MIN, max_length=SLIDES_MAX, description=f"카드 {SLIDES_MIN}~{SLIDES_MAX}장"),
    ]

    @field_validator("slides", mode="before")
    @classmethod
    def clip_slides(cls, value: object) -> object:
        """장수가 상한을 넘으면 뒤를 버린다(하한 미달은 그대로 실패시킨다 - 카드 2장은
        카드뉴스라고 부를 수 없어서 다시 생성하는 편이 낫다)."""
        if isinstance(value, list) and len(value) > SLIDES_MAX:
            return value[:SLIDES_MAX]
        return value


# ── API 응답/요청 DTO ──────────────────────────────────────────────────────────


class HealthNewsFeedItem(BaseModel):
    """뉴스 피드 목록의 한 줄. **본문(body_text)을 일부러 담지 않는다** - 피드에서는 안 쓰는데
    기사마다 1~3KB씩이라 목록 응답만 무겁게 만든다. 본문은 상세 조회에서 받는다."""

    id: int = Field(description="기사 ID(상세조회용)")
    title: str = Field(description="기사 제목")
    source_name: str = Field(description="화면에 표시할 매체명", examples=["코메디닷컴"])
    source_url: str = Field(description="원문 링크")
    published_at: datetime = Field(description="기사 발행 시각")
    image_url: str | None = Field(default=None, description="대표 이미지 URL(원본 서버 참조, 없을 수 있음)")
    has_card_summary: bool = Field(description="true면 [카드요약보기]를 대기 없이 열 수 있다")


class HealthNewsFeedResponse(BaseModel):
    items: list[HealthNewsFeedItem]


class HealthNewsDetailResponse(BaseModel):
    """상세화면. 카드요약이 함께 실려 오므로 [카드요약보기]를 눌러도 추가 요청이 없다."""

    id: int
    title: str
    source_name: str
    source_url: str = Field(description="원문 링크. AI 요약이 틀렸을 때 사용자가 확인할 수 있는 경로다")
    published_at: datetime
    body_text: str = Field(description='본문 평문. 단락은 빈 줄("\\n\\n")로 구분된다')
    image_url: str | None = None
    image_caption: str | None = Field(default=None, description="사진 설명(출처 표기가 들어있어 사진과 함께 보여준다)")
    card_summary: CardSummary | None = Field(
        default=None, description="카드뉴스 요약. null이면 아직 생성 전이므로 [카드요약보기]를 비활성으로 둔다"
    )
    disclaimer: str = Field(description="면책 문구(응답 시점에 항상 동적으로 부착됨, REQ-INFO-004)")


class AdminHealthNewsResponse(BaseModel):
    """관리자 목록. 어떤 카테고리로 수집됐는지 보여줘서 필터 기준을 조정할 근거로 쓴다."""

    model_config = {"from_attributes": True}

    id: int
    source: str
    source_name: str
    source_url: str
    title: str
    published_at: datetime
    image_url: str | None = None
    source_categories: list[str] | None = None
    disease_code: str | None = None
    has_card_summary: bool = Field(description="카드요약 생성 여부")
    fetched_at: datetime


class HealthNewsUpdateRequest(BaseModel):
    """관리자 수정. source/source_url은 유니크 제약 키라 받지 않는다."""

    title: str | None = Field(default=None, max_length=300)
    body_text: str | None = None


class CollectNewsResponse(BaseModel):
    """[뉴스 수집] 버튼 결과. 걸러낸 수를 따로 보여주는 이유: 조용히 버리면 "10건 중 6건만
    저장됨"이 필터 때문인지 파싱 실패인지 관리자가 알 수 없다."""

    fetched: int = Field(description="모든 매체의 피드에서 파싱된 기사 수(합계)")
    excluded: int = Field(description="건강정보가 아닌 카테고리라 저장하지 않은 수")
    created: int = Field(description="새로 저장한 수")
    skipped: int = Field(description="이미 있어서 건너뛴 수")
    over_limit: int = Field(
        0,
        description=(
            "매체당 상한을 넘어 이번에는 가져오지 않은 수. 버린 게 아니라 미룬 것이며 "
            "다음 수집에서 다시 후보가 된다. 상한은 카드요약 LLM 비용 상한 역할을 한다."
        ),
    )
    unreadable: int = Field(
        0,
        description=(
            "기사 페이지에서 본문을 뽑지 못해 버린 수. 0이 정상이고, 계속 늘어나면 "
            "상대 매체의 기사 페이지 구조가 바뀐 것이므로 파서를 봐야 한다."
        ),
    )
    collect_error: str | None = Field(
        None,
        description=(
            "매체 하나가 통째로 실패한 첫 원인 한 줄(피드가 죽었거나 형식이 깨진 경우). "
            "한 매체가 실패해도 나머지 매체는 계속 수집하므로 이 값이 유일한 단서다. 없으면 null."
        ),
    )
    pending_summaries: int = Field(
        0,
        description=(
            "수집이 끝난 뒤 카드요약이 아직 없는 기사 수. **수집 응답에는 요약 결과가 없다** - "
            "요약은 기사 1건당 4~5초라 수집과 한 요청에 묶으면 게이트웨이 타임아웃(504)을 맞는다"
            "(2026-07-31 실제로 겪음). 요약은 `/news/card-summaries/fill`을 이 수가 0이 될 때까지 "
            "여러 번 불러 채운다."
        ),
    )


class CardSummaryBatchResponse(BaseModel):
    """카드요약 배치 1회의 결과. `fill`(빈 것만 채우기)과 `regenerate`(전체 다시 만들기)가
    같은 모양을 쓴다 - 호출하는 화면이 둘 다 "남은 수가 0이 될 때까지 이어 부르기"로 똑같이
    다루기 때문이다.

    한 번에 몇 건을 처리하는지는 서버가 정한다(`CARD_SUMMARY_BATCH_SIZE`). 클라이언트가
    크게 요청해서 타임아웃을 자초할 수 없어야 한다."""

    attempted: int = Field(description="이번 배치에서 요약을 시도한 기사 수")
    generated: int = Field(description="요약을 새로 만든(또는 덮어쓴) 수")
    failed: int = Field(description="실패한 수. 실패한 기사는 기존 값이 그대로 남고 다음 배치에서 다시 시도된다")
    remaining: int = Field(
        0,
        description=(
            "이번 배치 뒤에 남은 기사 수. 0이 되면 멈춘다. "
            "**진행이 없는데(generated=0) 남아 있으면 멈춰야 한다** - 같은 기사가 계속 실패하는 "
            "상황이라 이어 불러도 무한히 반복된다."
        ),
    )
    next_offset: int = Field(
        0,
        description=(
            "다음 배치를 요청할 위치. `regenerate`에서만 의미가 있다 - 요약이 이미 있는 기사도 "
            "대상이라 진행 위치가 데이터에 남지 않으므로 호출하는 쪽이 들고 있어야 한다. "
            "`fill`은 요약이 빈 기사만 고르므로 언제나 0이다."
        ),
    )
    error: str | None = Field(
        None,
        description=(
            "실패한 첫 원인 한 줄(예외 종류 + 메시지, 최대 300자). 실패가 없으면 null. "
            "예외 종류만으로 원인이 갈린다 - AIWorkerUnavailableError면 ai_worker 호출 자체가 "
            "실패한 것이고, ValidationError면 호출은 됐지만 LLM 출력이 스키마에 못 미친 것이다. "
            "관리자 전용 응답이며 전체 트레이스백은 서버 로그에만 남는다."
        ),
    )
