import { useEffect, useRef, useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";

import { useOcrStage } from "./ocrStages";

export type OcrJobStatus = "pending" | "uploading" | "processing" | "done" | "failed";

interface OcrProgressBarProps {
  status: OcrJobStatus | null;
  /** 지정하면 자동 단계 문구 대신 이 텍스트를 고정으로 보여준다. */
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
  const stage = useOcrStage(isActive);

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
  const displayLabel =
    label ?? (isActive ? stage.label : status === "done" ? "분석 완료!" : "분석에 실패했습니다");
  const displayIcon = isActive ? stage.icon : status === "done" ? "✅" : "⚠️";

  return (
    <div style={{ width: "100%" }}>
      <style>{`
        @keyframes ocr-progress-icon-bounce {
          0%, 100% { transform: translateY(0) rotate(-8deg); }
          50% { transform: translateY(-4px) rotate(8deg); }
        }
      `}</style>
      <p
        style={{
          margin: "0 0 12px",
          fontSize: 13,
          fontWeight: 600,
          color: pinkTheme.text,
          textAlign: "center",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
        }}
      >
        <span aria-hidden>{displayIcon}</span>
        {displayLabel}
      </p>
      <div style={{ position: "relative", width: "100%", height: 10, marginTop: 16 }}>
        <div
          style={{
            width: "100%",
            height: "100%",
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
        {/* 진행률(percent)을 따라 가로로 이동(transition)하는 현재 단계 아이콘. 이동 중 위아래로
            통통 튀는 연출은 별도 keyframe 애니메이션으로 분리해서 transform 속성이 안 겹치게 했다. */}
        <div
          style={{
            position: "absolute",
            left: `${percent}%`,
            top: -14,
            transform: "translateX(-50%)",
            transition: "left 0.2s ease-out",
          }}
        >
          <span
            aria-hidden
            style={{
              display: "inline-block",
              fontSize: 20,
              animation: isActive ? "ocr-progress-icon-bounce 0.6s ease-in-out infinite" : "none",
            }}
          >
            {displayIcon}
          </span>
        </div>
      </div>
    </div>
  );
}
