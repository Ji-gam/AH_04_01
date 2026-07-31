"""T-LLM-6 카드요약 스키마의 방어 동작 테스트.

이 스키마는 LLM 응답을 받는 자리라 "틀린 응답이 와도 카드를 잃지 않는다"가 핵심 요구사항이다.
ai_worker는 함수호출 방식으로 생성하므로 스키마의 maxLength가 LLM에게 강제되지 않고 권고로만
전달된다 - 그래서 넘치는 값은 거절이 아니라 잘라내야 한다.

여기 테스트는 모두 실제 LLM 호출로 겪은 현상을 고정한 것이다(2026-07-30, 기사 7건/카드 31장).
"""

import pytest
from pydantic import ValidationError

from app.dtos.health_news_dto import (
    FALLBACK_ICON_KEY,
    ICON_KEYS,
    SLIDES_MAX,
    STAT_MAX,
    TAG_MAX,
    TEXT_MAX,
    CardSlide,
    CardSummary,
)


def _slide(**overrides: object) -> dict:
    base: dict = {"icon_key": "moon", "tag": "수면", "stat": "+1시간", "text": "잠이 늘면 혈당이 안정됩니다."}
    base.update(overrides)
    return base


def test_icon_keys_derive_from_the_literal() -> None:
    """Literal이 유일한 원본이고 ICON_KEYS는 거기서 뽑는다 - 두 곳을 따로 관리하면 어긋난다."""
    assert len(ICON_KEYS) == len(set(ICON_KEYS))
    assert FALLBACK_ICON_KEY in ICON_KEYS


def test_unknown_icon_falls_back_instead_of_failing() -> None:
    """LLM이 목록에 없는 아이콘을 답해도 카드를 잃지 않는다 - 중립 아이콘으로 바꾼다."""
    slide = CardSlide.model_validate(_slide(icon_key="unicorn-sparkle"))

    assert slide.icon_key == FALLBACK_ICON_KEY


def test_overlong_text_is_clipped_not_rejected() -> None:
    slide = CardSlide.model_validate(_slide(text="가" * (TEXT_MAX + 40)))

    assert len(slide.text) == TEXT_MAX


def test_overlong_tag_and_stat_are_clipped() -> None:
    slide = CardSlide.model_validate(_slide(tag="가" * (TAG_MAX + 5), stat="9" * (STAT_MAX + 5)))

    assert len(slide.tag) == TAG_MAX
    assert slide.stat is not None
    assert len(slide.stat) == STAT_MAX


def test_blank_stat_becomes_none() -> None:
    """실측(31장 중 3장): LLM은 "값 없음"을 None이 아니라 ""로 답한다. 그대로 두면 카드에서
    가장 큰 글씨 자리가 빈칸으로 그려진다."""
    assert CardSlide.model_validate(_slide(stat="")).stat is None
    assert CardSlide.model_validate(_slide(stat="   ")).stat is None


def test_blank_substat_becomes_none() -> None:
    assert CardSlide.model_validate(_slide(substat="")).substat is None


def test_stat_may_be_omitted_entirely() -> None:
    """숫자가 없는 카드를 억지로 숫자로 만들게 강요하면 LLM이 없는 숫자를 지어낸다 -
    건강 정보에서는 빈칸보다 나쁘다. 그래서 stat 없는 카드를 정식으로 허용한다."""
    payload = _slide()
    del payload["stat"]

    assert CardSlide.model_validate(payload).stat is None


def test_extra_slides_are_dropped_to_the_limit() -> None:
    summary = CardSummary.model_validate({"slides": [_slide() for _ in range(SLIDES_MAX + 3)]})

    assert len(summary.slides) == SLIDES_MAX


def test_too_few_slides_is_rejected_so_the_batch_retries() -> None:
    """카드 2장은 카드뉴스라고 부를 수 없다 - 잘못 채워두는 대신 실패시켜서 다음 실행이
    다시 생성하게 한다(`card_summary`가 비어 있으면 재시도 대상이 된다)."""
    with pytest.raises(ValidationError):
        CardSummary.model_validate({"slides": [_slide(), _slide()]})
