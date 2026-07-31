import { useEffect, useRef, useState } from "react";

export interface OcrStage {
  icon: string;
  label: string;
}

/** 백엔드가 pending/processing 같은 상태값만 주고 세부 진행 단계는 안 주기 때문에,
 * 경과 시간을 기준으로 "지금 이런 걸 하고 있다"는 문구를 순서대로 흉내내서 보여준다.
 * 실제 처리 순서와는 무관한 연출용 단계이며, 마지막 단계에서는 done/failed가 올 때까지 머문다. */
export const OCR_STAGES: OcrStage[] = [
  { icon: "🔬", label: "처방전을 읽고 있습니다..." },
  { icon: "🔬", label: "약 성분을 확인하고 있습니다..." },
  { icon: "💊", label: "약 정보를 매칭하고 있습니다..." },
  { icon: "📅", label: "복약 시간표를 준비하고 있습니다..." },
  { icon: "⏳", label: "거의 다 됐어요..." },
];

// OCR_STAGES[i]에서 OCR_STAGES[i+1]로 넘어가기까지 걸리는 시간(ms). 마지막 단계는 별도 지속시간 없이 유지.
// 누적 전환 시점: 2초 → 5초 → 8초 → 11초
const STAGE_DURATIONS_MS = [2000, 3000, 3000, 3000];

export function useOcrStage(isActive: boolean): OcrStage {
  const [stageIndex, setStageIndex] = useState(0);
  const startRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isActive) {
      setStageIndex(0);
      startRef.current = null;
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    startRef.current = Date.now();
    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - (startRef.current ?? Date.now());
      let cumulative = 0;
      let idx = STAGE_DURATIONS_MS.length;
      for (let i = 0; i < STAGE_DURATIONS_MS.length; i++) {
        cumulative += STAGE_DURATIONS_MS[i];
        if (elapsed < cumulative) {
          idx = i;
          break;
        }
      }
      setStageIndex(Math.min(idx, OCR_STAGES.length - 1));
    }, 500);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isActive]);

  return OCR_STAGES[stageIndex];
}
