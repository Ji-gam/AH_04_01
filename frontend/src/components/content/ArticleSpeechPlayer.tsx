/**
 * T-ACC-1 낭독 플레이어. 기사 상세화면 하단에 붙어 재생 상태와 조작 버튼을 보여준다.
 *
 * TRD T-ACC-1 성공요건 중 "재생 상태 표시"와 "정지 버튼으로 즉시 중단"이 이 컴포넌트의 몫이다.
 * 실제 재생 로직은 `useArticleSpeech`가 갖고 있고 여기는 표시만 한다.
 *
 * [화면 맨 아래가 아니라 스크롤 영역 맨 아래에 붙는다] 앱 하단에는 항상 보이는 BottomNav가
 * 있어서 `position: fixed`로 깔면 탭 바를 가린다. 그래서 `sticky bottom-0`으로 상세화면의
 * 스크롤 영역 안쪽 맨 아래에 붙인다 - 스크롤해도 따라오지만 탭 바를 침범하지 않는다.
 *
 * [고령 사용자 기준] PRD F-ACC-1이 이 기능을 접근성 기능으로 규정하고 있어, 버튼을 작게
 * 욱여넣지 않고 터치 영역을 넉넉히 잡았다.
 */
import { Pause, Play, Square, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { SpeechRate, SpeechStatus } from "@/hooks/useArticleSpeech";
import { cn } from "@/lib/utils";

const RATE_LABELS: ReadonlyArray<{ value: SpeechRate; label: string }> = [
  { value: "slow", label: "느리게" },
  { value: "normal", label: "보통" },
  { value: "fast", label: "빠르게" },
];

interface ArticleSpeechPlayerProps {
  status: SpeechStatus;
  spokenParagraphNumber: number;
  paragraphCount: number;
  rate: SpeechRate;
  onRateChange: (rate: SpeechRate) => void;
  onResume: () => void;
  onPause: () => void;
  onStop: () => void;
}

export function ArticleSpeechPlayer({
  status,
  spokenParagraphNumber,
  paragraphCount,
  rate,
  onRateChange,
  onResume,
  onPause,
  onStop,
}: ArticleSpeechPlayerProps) {
  const isSpeaking = status === "speaking";

  // 제목을 읽는 중에는 아직 단락 번호가 없다(0). 숫자를 0으로 보여주면 오해를 사서 문구를 바꾼다.
  const progressText =
    spokenParagraphNumber === 0
      ? "제목을 읽고 있어요"
      : `${spokenParagraphNumber} / ${paragraphCount} 단락`;

  return (
    <div
      role="group"
      aria-label="기사 음성 재생"
      // `bg-background`은 불투명해야 한다 - 투명하면 뒤로 지나가는 본문이 겹쳐 보인다.
      // 색은 index.css의 디자인 토큰만 쓴다(FRONTEND_UI_GUIDE_v1.0.md 2번). `bg-secondary`는
      // 읽는 중인 단락 하이라이트가 쓰고 있어서 헷갈리지 않게 피했다.
      className="sticky bottom-0 z-20 mt-3 border-t border-border bg-background px-4 py-3 shadow-[0_-2px_8px_rgba(0,0,0,0.08)]"
    >
      <div className="flex items-center gap-2">
        <Volume2 size={16} className="shrink-0 text-primary" aria-hidden />
        <p aria-live="polite" className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          {isSpeaking ? "재생 중" : "일시정지"} · {progressText}
        </p>

        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={isSpeaking ? onPause : onResume}
          aria-label={isSpeaking ? "일시정지" : "이어듣기"}
          className="h-9 w-9 shrink-0 p-0"
        >
          {isSpeaking ? <Pause size={16} aria-hidden /> : <Play size={16} aria-hidden />}
        </Button>

        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={onStop}
          aria-label="정지"
          className="h-9 w-9 shrink-0 p-0"
        >
          <Square size={14} aria-hidden />
        </Button>
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        <span className="text-[11px] text-muted-foreground">속도</span>
        {RATE_LABELS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onRateChange(option.value)}
            aria-pressed={rate === option.value}
            className={cn(
              "rounded-full px-2.5 py-1 text-[11px] transition-colors",
              rate === option.value
                ? "bg-primary text-primary-foreground"
                : "bg-secondary text-secondary-foreground",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
