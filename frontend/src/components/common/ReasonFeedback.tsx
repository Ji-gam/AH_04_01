import { useState } from "react";

import type { ReasonFeedbackValue } from "../../api/types";
import { pinkTheme as t } from "../../theme/pinkTheme";

interface Props {
  onSubmit: (value: ReasonFeedbackValue) => Promise<unknown>;
}

/** 습관/식단 이유 문구 아래 붙는 작은 👍/👎 피드백 위젯 - AI/규칙 기반으로 생성되는 한 줄
 * 설명이 실제로 도움이 되는지 확인할 방법이 없다는 문제를 해소한다. 값을 누르면 그대로
 * onSubmit에 위임하고(백엔드 upsert라 재평가 가능), 실패해도 이미 보여준 이유 화면 흐름을
 * 막지 않도록 조용히 무시한다. */
export default function ReasonFeedback({ onSubmit }: Props) {
  const [value, setValue] = useState<ReasonFeedbackValue | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleClick = async (next: ReasonFeedbackValue) => {
    if (submitting || value === next) return;
    setSubmitting(true);
    try {
      await onSubmit(next);
      setValue(next);
    } catch {
      // 피드백은 부가 기능 - 실패해도 조용히 무시한다.
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
      <span style={{ fontSize: 11, color: t.textMuted }}>이 설명이 도움이 됐나요?</span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          void handleClick("UP");
        }}
        disabled={submitting}
        aria-label="도움이 됐어요"
        aria-pressed={value === "UP"}
        style={{
          border: "none",
          background: "none",
          cursor: submitting ? "default" : "pointer",
          fontSize: 13,
          opacity: value === "DOWN" ? 0.4 : 1,
          padding: 2,
        }}
      >
        👍
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          void handleClick("DOWN");
        }}
        disabled={submitting}
        aria-label="도움이 안 됐어요"
        aria-pressed={value === "DOWN"}
        style={{
          border: "none",
          background: "none",
          cursor: submitting ? "default" : "pointer",
          fontSize: 13,
          opacity: value === "UP" ? 0.4 : 1,
          padding: 2,
        }}
      >
        👎
      </button>
      {value && <span style={{ fontSize: 11, color: t.primary }}>감사합니다!</span>}
    </div>
  );
}
