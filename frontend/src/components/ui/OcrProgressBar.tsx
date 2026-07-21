import { useEffect, useRef, useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";

export type OcrJobStatus = "pending" | "uploading" | "processing" | "done" | "failed";

interface OcrProgressBarProps {
  status: OcrJobStatus | null;
  label?: string;
}

/** 백엔드가 pending/processing 같은 상태값만 주고 실제 진행률(%)은 안 주기 때문에,
 * 진행 중인 동안 90%까지는 점점 느려지는 곡선으로 자체적으로 채워나가다가(사용자가
 * "멈춘 것 아닌가" 불안해하지 않게) done이 오면 바로 100%로 채운다. 실제 진행률이
 * 아니라 "지금 뭔가 진행되고 있다"는 심리적 안심용 표시라 이 정도로 충분하다. */
export default function OcrProgressBar({ status, label }: OcrProgressBarProps) {
  const [percent, setPercent] = useState(0);
  const rafRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isActive = status === "pending" || status === "uploading" || status === "processing";

  useEffect(() => {
    if (isActive) {
      setPercent((p) => (p <= 0 ? 4 : p));
      rafRef.current = setInterval(() => {
        setPercent((p) => (p >= 92 ? p : p + (92 - p) * 0.08));
      }, 200);
    } else if (status === "done") {
      setPercent(100);
    } else if (status === "failed") {
      // 실패 시점 진행률을 그대로 두고 색만 바꿔서 "여기서 멈췄다"를 보여준다.
    } else {
      setPercent(0);
    }
    return () => {
      if (rafRef.current) clearInterval(rafRef.current);
    };
  }, [isActive, status]);

  if (!status) return null;

  const barColor = status === "failed" ? pinkTheme.danger : pinkTheme.primary;

  return (
    <div style={{ width: "100%" }}>
      {label && (
        <p style={{ margin: "0 0 6px", fontSize: 12, color: pinkTheme.textMuted }}>{label}</p>
      )}
      <div
        style={{
          width: "100%",
          height: 8,
          borderRadius: 999,
          background: pinkTheme.primarySoft,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${percent}%`,
            height: "100%",
            borderRadius: 999,
            background: barColor,
            transition: "width 0.2s ease-out, background-color 0.2s ease-out",
          }}
        />
      </div>
    </div>
  );
}
