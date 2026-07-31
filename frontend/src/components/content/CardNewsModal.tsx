/**
 * T-LLM-6 카드뉴스 모달. 기사 상세에서 [카드요약보기]를 누르면 열린다.
 *
 * 프로토타입(docs/dev/sample_card_news/)을 그대로 옮긴 것이고, 두 곳만 바꿨다.
 *
 * 1. 카드 폭을 `291px` 하드코딩에서 **실측한 덱 폭으로 계산**하게 바꿨다. 프로토타입은
 *    351px 화면 기준으로 `351 - 2*(peek 16 + gap 14) = 291`을 손으로 역산한 값이라 화면 폭이
 *    달라지면 peek이 어긋난다.
 *    (처음엔 `flex: 0 0 100%`로 CSS만으로 풀려고 했는데, 375px 화면에서 기대한 315px이 아니라
 *    355px로 계산됐다 — 퍼센트 flex-basis가 무엇을 기준으로 풀리는지가 스크롤 컨테이너 +
 *    aspect-ratio 조합에서 모호했다. 그래서 ResizeObserver로 덱 폭을 직접 재서 CSS 변수에
 *    넣는다. 계산식이 코드에 그대로 드러나 검증도 쉽다.)
 * 2. `stat`이 없는 카드(기사에 마땅한 숫자가 없는 경우)를 "글자 카드"로 그린다 — 그 자리를
 *    비워두면 카드 중앙이 텅 빈다.
 *
 * 표지/면책 카드는 LLM이 만들지 않는다. 면책 문구가 LLM 손에 달려 있으면 안 되고(REQ-INFO-004),
 * 표지는 기사 제목만 있으면 충분하다.
 */
import { X } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";

import type { HealthNewsDetailResult } from "../../api/types";

import { cardGradient, cardNewsIcon } from "@/lib/cardNewsIcons";

type Props = {
  news: HealthNewsDetailResult;
  onClose: () => void;
};

// 카드 좌우로 다음/이전 카드가 이만큼만 보이게 한다(프로토타입에서 확정한 값).
const PEEK_PX = 16;
const GAP_PX = 14;

export function CardNewsModal({ news, onClose }: Props) {
  const deckRef = useRef<HTMLDivElement>(null);
  const slides = news.card_summary?.slides ?? [];

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  // 카드 폭을 덱 폭에서 역산해 CSS 변수로 넣는다. 카드가 화면 가운데에 스냅됐을 때
  // 좌우로 PEEK_PX씩만 다음/이전 카드가 보이게 하는 폭이다:
  //   peek = deckW/2 - cardW/2 - GAP  →  cardW = deckW - 2*(PEEK + GAP)
  // 화면 회전이나 창 크기 변경에도 따라가도록 ResizeObserver로 다시 잰다.
  useEffect(() => {
    const deck = deckRef.current;
    if (!deck) return;

    const applyCardWidth = () => {
      const cardWidth = deck.clientWidth - 2 * (PEEK_PX + GAP_PX);
      deck.style.setProperty("--cardnews-card-w", `${Math.max(cardWidth, 200)}px`);
    };

    applyCardWidth();
    const observer = new ResizeObserver(applyCardWidth);
    observer.observe(deck);
    return () => observer.disconnect();
  }, []);

  // 데스크톱 마우스는 스와이프가 없어서 드래그로 스크롤되게 직접 붙인다. 터치는 브라우저의
  // 기본 스크롤이 이미 잘 동작하므로 건드리지 않는다(pointerType으로 갈라낸다).
  useEffect(() => {
    const deck = deckRef.current;
    if (!deck) return;

    let isDown = false;
    let moved = false;
    let startX = 0;
    let startScroll = 0;

    const cardStep = () => {
      const cards = deck.querySelectorAll<HTMLElement>("[data-card]");
      return cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : deck.clientWidth;
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.pointerType !== "mouse") return;
      isDown = true;
      moved = false;
      startX = event.clientX;
      startScroll = deck.scrollLeft;
      deck.classList.add("is-dragging");
      deck.setPointerCapture(event.pointerId);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!isDown) return;
      const dx = event.clientX - startX;
      if (Math.abs(dx) > 3) moved = true;
      deck.scrollLeft = startScroll - dx;
    };

    const endDrag = () => {
      if (!isDown) return;
      isDown = false;
      deck.classList.remove("is-dragging");
      // 스냅을 끄고 드래그했으므로, 손을 떼면 가장 가까운 카드로 직접 되돌려놓는다.
      const step = cardStep();
      const index = Math.round(deck.scrollLeft / step);
      deck.scrollTo({ left: index * step, behavior: "smooth" });
    };

    // 드래그로 끝난 포인터 조작이 클릭으로도 해석되면, 카드 위의 링크가 의도치 않게 열린다.
    const suppressClickAfterDrag = (event: MouseEvent) => {
      if (!moved) return;
      event.preventDefault();
      event.stopPropagation();
      moved = false;
    };

    deck.addEventListener("pointerdown", onPointerDown);
    deck.addEventListener("pointermove", onPointerMove);
    deck.addEventListener("pointerup", endDrag);
    deck.addEventListener("pointercancel", endDrag);
    deck.addEventListener("click", suppressClickAfterDrag, true);

    return () => {
      deck.removeEventListener("pointerdown", onPointerDown);
      deck.removeEventListener("pointermove", onPointerMove);
      deck.removeEventListener("pointerup", endDrag);
      deck.removeEventListener("pointercancel", endDrag);
      deck.removeEventListener("click", suppressClickAfterDrag, true);
    };
  }, []);

  const restart = useCallback(() => {
    const deck = deckRef.current;
    if (!deck) return;
    deck.scrollTo({ left: 0, behavior: "smooth" });
    // 일부 환경에서 smooth 스크롤이 씹히는 경우가 있어, 목표 위치가 아니면 즉시 이동으로 보정한다.
    window.setTimeout(() => {
      if (deck.scrollLeft !== 0) deck.scrollLeft = 0;
    }, 400);
  }, []);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="카드 요약"
      className="fixed inset-0 z-50 flex flex-col bg-black/70 backdrop-blur-sm"
    >
      <style>{`
        .cardnews-deck {
          scroll-snap-type: x mandatory;
          scroll-padding-inline: ${PEEK_PX + GAP_PX}px;
          padding-inline: ${PEEK_PX + GAP_PX}px;
          gap: ${GAP_PX}px;
          overflow-anchor: none;
          scrollbar-width: none;
          touch-action: pan-x;
          cursor: grab;
        }
        .cardnews-deck::-webkit-scrollbar { display: none; }
        .cardnews-deck.is-dragging { cursor: grabbing; scroll-snap-type: none; }
        /* --cardnews-card-w는 위 useEffect가 덱 폭을 재서 넣는다(계산식은 거기 주석 참고).
           변수가 아직 없을 때를 대비한 폴백은 프로토타입 기준값(291px)이다.

           box-sizing을 명시하는 이유: 이 프로젝트는 Tailwind Preflight를 꺼놨기 때문에
           전역 border-box 리셋이 없다. 기본값 content-box로 계산되면 좌우 패딩(px-5 = 20px씩)이
           폭에 더해져 315px로 지정한 카드가 355px로 그려지고, 그만큼 peek이 사라진다(실측 확인).
           전역으로 되돌리면 아직 마이그레이션 안 된 화면들이 깨지므로 이 카드에만 국소로 지정한다. */
        .cardnews-card {
          box-sizing: border-box;
          flex: 0 0 var(--cardnews-card-w, 291px);
          scroll-snap-align: center;
        }
      `}</style>

      <div className="flex items-center justify-between px-4 pt-[calc(env(safe-area-inset-top)+12px)] pb-1">
        <p className="text-sm font-semibold text-white/90">카드 요약</p>
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="flex h-9 w-9 items-center justify-center rounded-full border-none bg-white/15 text-white"
        >
          <X size={18} />
        </button>
      </div>

      <div
        ref={deckRef}
        className="cardnews-deck flex flex-1 select-none items-center overflow-x-auto"
      >
        {/* 표지 — 기사 제목. LLM이 만들지 않는다. */}
        <article
          data-card
          className="cardnews-card relative flex aspect-[3/4] flex-col justify-end overflow-hidden rounded-[28px] px-5 pb-6 text-white shadow-[0_20px_40px_-14px_rgba(0,0,0,0.55)]"
          style={{ background: cardGradient(0) }}
        >
          <span className="absolute inset-0 rounded-[inherit] bg-gradient-to-t from-black/55 via-black/10 to-transparent" />
          <div className="relative">
            <p className="mb-2 text-xs font-bold opacity-90">{news.source_name}</p>
            <h2 className="text-2xl font-extrabold leading-snug text-balance">{news.title}</h2>
            <p className="mt-3 text-xs opacity-85">넘겨서 요약 보기 →</p>
          </div>
        </article>

        {slides.map((slide, index) => {
          const Icon = cardNewsIcon(slide.icon_key);
          // stat이 없는 카드는 설명 문장을 큰 글씨로 올려 카드 중앙이 비지 않게 한다.
          const isTextOnly = !slide.stat;
          return (
            <article
              key={`${slide.icon_key}-${index}`}
              data-card
              className="cardnews-card relative flex aspect-[3/4] flex-col justify-end overflow-hidden rounded-[28px] px-5 pb-6 text-white shadow-[0_20px_40px_-14px_rgba(0,0,0,0.55)]"
              style={{ background: cardGradient(index + 1) }}
            >
              {/* 배경 워터마크 — 같은 아이콘을 크게 옅게. 이미지 파일이 없어도 배경이 비지 않는다. */}
              <Icon
                aria-hidden
                strokeWidth={0.6}
                className="pointer-events-none absolute -right-6 top-10 h-52 w-52 opacity-[0.16]"
              />
              {/* 워터마크 위, 본문 아래에 깔리는 그늘 — 글자 가독성용. */}
              <span className="absolute inset-0 z-[1] rounded-[inherit] bg-gradient-to-t from-black/55 via-black/10 to-transparent" />

              <div className="relative z-[2] mb-auto mt-5 flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-full bg-white/[0.16] shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_6px_14px_rgba(0,0,0,0.18)]">
                <Icon aria-hidden size={26} strokeWidth={1.9} />
              </div>

              <div className="relative z-[2]">
                <p className="mb-1.5 text-xs font-bold uppercase tracking-wide opacity-90">
                  {slide.tag}
                </p>
                {isTextOnly ? (
                  <p className="text-xl font-extrabold leading-snug text-balance">{slide.text}</p>
                ) : (
                  <>
                    <p className="text-[32px] font-extrabold leading-none">{slide.stat}</p>
                    {slide.substat && (
                      <p className="mt-1.5 text-sm font-semibold opacity-90">{slide.substat}</p>
                    )}
                    <p className="mt-2.5 text-sm leading-snug opacity-95">{slide.text}</p>
                  </>
                )}
              </div>
            </article>
          );
        })}

        {/* 마지막 카드 — 면책 + AI 요약 표기 + 원문. 코드가 직접 그린다(LLM에 맡기지 않는다). */}
        <article
          data-card
          className="cardnews-card relative flex aspect-[3/4] flex-col justify-center gap-4 overflow-hidden rounded-[28px] bg-white px-6 py-6 text-center shadow-[0_20px_40px_-14px_rgba(0,0,0,0.55)]"
        >
          <p className="text-sm font-bold text-foreground">
            이 요약은 AI가 기사를 정리한 것입니다.
            <br />
            정확한 내용은 원문을 확인해주세요.
          </p>
          <a
            href={news.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-primary underline underline-offset-2"
          >
            {news.source_name} 원문 보기
          </a>
          <p className="text-xs leading-relaxed text-muted-foreground">{news.disclaimer}</p>
          <button
            type="button"
            onClick={restart}
            className="mx-auto rounded-full border border-border bg-secondary px-4 py-2 text-xs font-semibold text-secondary-foreground"
          >
            처음부터 다시보기
          </button>
        </article>
      </div>

      <p className="px-6 pb-[calc(env(safe-area-inset-bottom)+14px)] pt-2 text-center text-xs text-white/70">
        좌우로 넘겨 보세요
      </p>
    </div>
  );
}
