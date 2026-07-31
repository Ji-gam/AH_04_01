/**
 * 건강정보 상세화면 — T-LLM-6. /info/:id.
 *
 * 사용자 여정 2~4단계에 해당한다: 원문이 길게 나오고, [카드요약보기]로 카드뉴스 모달을 열고,
 * [음성으로듣기]로 원문을 소리로 듣는다(T-ACC-1).
 *
 * 본문은 평문(`body_text`)이고 단락은 빈 줄로 구분돼 있다. 백엔드가 수집 시점에 HTML을
 * 걷어내므로 여기서 dangerouslySetInnerHTML을 쓸 필요가 없다 — 외부 사이트가 우리 앱에
 * 스크립트를 심는 통로를 만들지 않기 위한 설계다.
 *
 * [단락 쪼개기를 직접 하지 않는 이유] 화면 렌더링과 낭독이 **같은 `splitParagraphs`를 써야**
 * 하이라이트가 맞는 단락을 가리킨다(T-ACC-1). 여기서 따로 `split("\n\n")`을 하면 규칙이
 * 갈라지는 순간 하이라이트가 엉뚱한 곳으로 튄다.
 */
import { Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { healthNewsApi } from "../../api/healthNewsApi";
import type { HealthNewsDetailResult } from "../../api/types";

import { ArticleSpeechPlayer } from "@/components/content/ArticleSpeechPlayer";
import { CardNewsModal } from "@/components/content/CardNewsModal";
import { ShareSheet } from "@/components/content/ShareSheet";
import { Button } from "@/components/ui/button";
import { useArticleSpeech } from "@/hooks/useArticleSpeech";
import { splitParagraphs } from "@/lib/ttsText";
import { cn } from "@/lib/utils";

/** 하단 낭독 플레이어가 덮는 대략적인 높이(px). 자동 스크롤이 그 아래를 "보인다"고 착각하지
 *  않게 하려는 값이라, 정확할 필요는 없고 실제보다 조금 넉넉하면 된다. */
const PLAYER_HEIGHT_PX = 96;

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}.${date.getMonth() + 1}.${date.getDate()}`;
}

export default function InfoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const newsId = Number(id);

  const [item, setItem] = useState<HealthNewsDetailResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [isCardOpen, setIsCardOpen] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 훅은 조건부로 호출할 수 없어서 아래 early return보다 먼저 부른다. 기사가 아직 없으면
  // 빈 문자열이 들어가고, 조각이 0개라 재생 시작 자체가 막힌다.
  const speech = useArticleSpeech(item?.title ?? "", item?.body_text ?? "");
  const { currentParagraphIndex, status: speechStatus } = speech;

  useEffect(() => {
    if (!Number.isFinite(newsId)) {
      setIsLoading(false);
      setNotFound(true);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setNotFound(false);
    setItem(null);

    healthNewsApi
      .getById(newsId)
      .then((data) => {
        if (!cancelled) setItem(data);
      })
      .catch(() => {
        if (!cancelled) setNotFound(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [newsId]);

  // 읽고 있는 단락을 화면 안으로 끌어온다. 기사가 26단락쯤 되기 때문에 하이라이트만 칠하면
  // 곧 화면 밖으로 밀려나 "어디를 읽고 있는지"(PRD F-ACC-1)를 볼 수 없다.
  useEffect(() => {
    if (speechStatus !== "speaking" || currentParagraphIndex === null) return;

    const scroller = scrollRef.current;
    const target = bodyRef.current?.querySelector<HTMLElement>(
      `[data-paragraph="${currentParagraphIndex}"]`,
    );
    if (!scroller || !target) return;

    const view = scroller.getBoundingClientRect();
    const box = target.getBoundingClientRect();
    // 이미 다 보이면 건드리지 않는다 - 짧은 단락이 이어질 때 매번 화면이 튀지 않게. 하단
    // 플레이어가 덮는 높이는 "보이는 것"으로 치지 않는다.
    if (box.top >= view.top && box.bottom <= view.bottom - PLAYER_HEIGHT_PX) return;

    // `behavior: "smooth"`는 쓰지 않는다 - 브라우저나 기기 설정(동작 줄이기)에 따라 스크롤이
    // 아예 일어나지 않는 경우를 확인했다. 접근성 기능이라 부드러움보다 확실함이 먼저다.
    target.scrollIntoView({ block: "center" });
  }, [currentParagraphIndex, speechStatus]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      </div>
    );
  }

  if (notFound || !item) {
    return (
      <div className="flex h-full flex-col px-4 pt-[calc(env(safe-area-inset-top)+12px)]">
        <Link to="/info" className="mb-4 text-sm text-muted-foreground no-underline">
          ← 뒤로가기
        </Link>
        <p className="py-8 text-center text-sm text-muted-foreground">기사를 찾을 수 없어요.</p>
      </div>
    );
  }

  const paragraphs = splitParagraphs(item.body_text);
  const isPlayerVisible = speechStatus === "speaking" || speechStatus === "paused";
  // 음성 기능이 아예 없거나(구형 브라우저) 시작했는데 소리가 나지 않은 경우(아이폰 standalone
  // 무음 등). 버튼을 죽이지 않고 안내로 격하해서 화면이 깨지지 않게 한다.
  const isSpeechUnavailable = speechStatus === "unsupported" || speech.failed;

  return (
    <>
      <div ref={scrollRef} className="flex h-full flex-col overflow-y-auto">
        <div className="relative">
          <Link
            to="/info"
            aria-label="뒤로가기"
            className="absolute left-3.5 top-[calc(env(safe-area-inset-top)+12px)] z-10 flex h-8 w-8 items-center justify-center rounded-full bg-secondary text-secondary-foreground no-underline"
          >
            ‹
          </Link>
          {item.image_url && (
            <img src={item.image_url} alt="" className="aspect-[4/3] w-full object-cover" />
          )}
        </div>

        {/* figcaption에 "사진=게티이미지뱅크" 같은 출처 표기가 들어있어 사진과 함께 보여준다. */}
        {item.image_caption && (
          <p className="mx-4 mt-2 text-[11px] leading-snug text-muted-foreground">
            {item.image_caption}
          </p>
        )}

        <h1 className="mx-4 mt-4 text-xl font-bold text-balance">{item.title}</h1>

        <p className="mx-4 mt-1.5 text-xs text-muted-foreground">
          {item.source_name} · {formatDate(item.published_at)}
        </p>

        <div className="mx-4 mt-4 flex gap-2">
          <Button
            type="button"
            size="sm"
            onClick={() => setIsCardOpen(true)}
            disabled={!item.card_summary}
            className="flex-1"
          >
            {item.card_summary ? "카드요약보기" : "카드요약 준비중"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            // 아이폰은 클릭 핸들러 안에서 곧바로 발화가 시작되어야 한다 - start()/stop()을
            // await 없이 동기로 부른다. 여기에 비동기를 끼우면 아이폰에서 무음이 된다.
            onClick={isPlayerVisible ? speech.stop : speech.start}
            disabled={isSpeechUnavailable}
            className="flex-1"
            title={isSpeechUnavailable ? "이 기기에서는 음성 재생이 어려워요" : undefined}
          >
            <Volume2 size={15} className="mr-1" aria-hidden />
            {isSpeechUnavailable
              ? "음성 지원 안 됨"
              : isPlayerVisible
                ? "낭독 멈추기"
                : "음성으로듣기"}
          </Button>
        </div>

        {isSpeechUnavailable && (
          <p className="mx-4 mt-2 text-[11px] leading-snug text-muted-foreground">
            이 기기에서는 음성 재생이 어려워요. 다른 브라우저에서 다시 시도해 보세요.
          </p>
        )}

        <div ref={bodyRef} className="mx-4 mt-5 flex flex-col gap-3.5">
          {paragraphs.map((paragraph, index) => (
            <p
              key={index}
              data-paragraph={index}
              // 배경만 바꾼다 - 글꼴 굵기나 여백을 함께 바꾸면 하이라이트가 옮겨질 때마다
              // 글자가 밀려서 읽던 자리를 놓친다.
              className={cn(
                "-mx-2 rounded-md px-2 py-1 text-sm leading-relaxed text-foreground transition-colors",
                index === currentParagraphIndex && "bg-secondary",
              )}
            >
              {paragraph}
            </p>
          ))}
        </div>

        <a
          href={item.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mx-4 mt-5 text-xs text-primary underline underline-offset-2"
        >
          {item.source_name}에서 원문 보기
        </a>

        <p className="mx-4 mt-4 text-xs text-muted-foreground">{item.disclaimer}</p>

        <div className="mb-10 mt-5 flex justify-center">
          <ShareSheet title={item.title} />
        </div>

        {/* 스크롤 영역 안쪽 맨 아래에 붙는다(sticky). 앱 하단 탭 바를 가리지 않기 위해서다. */}
        {isPlayerVisible && (
          <ArticleSpeechPlayer
            status={speechStatus}
            spokenParagraphNumber={speech.spokenParagraphNumber}
            paragraphCount={speech.paragraphCount}
            rate={speech.rate}
            onRateChange={speech.setRate}
            onResume={speech.resume}
            onPause={speech.pause}
            onStop={speech.stop}
          />
        )}
      </div>

      {isCardOpen && item.card_summary && (
        <CardNewsModal news={item} onClose={() => setIsCardOpen(false)} />
      )}
    </>
  );
}
