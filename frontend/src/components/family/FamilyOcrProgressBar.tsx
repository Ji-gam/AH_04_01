import { useEffect, useRef, useState } from "react";

import { pinkTheme } from "../../theme/pinkTheme";
import { useOcrStage } from "../ui/ocrStages";

export type FamilyOcrJobStatus = "pending" | "uploading" | "processing" | "done" | "failed";

interface FamilyOcrProgressBarProps {
  status: FamilyOcrJobStatus | null;
  /** 지정하면 자동 단계 문구 대신 이 텍스트를 고정으로 보여준다. */
  label?: string;
}

/** [가족관리 전용] 처방전 인식 중 로딩 표시. 기존 공용 `components/ui/OcrProgressBar`와
 * 진행률 채우기 로직(백엔드가 실제 %를 안 줘서, 92%까지 점점 느려지는 곡선으로 자체
 * 채움)은 동일하게 가져오되, 알약 아이콘이 진행률을 따라 이동하면서 위아래로 통통 튀는
 * 연출을 추가했다. 공용 컴포넌트를 고치면 본인 몫 화면(MedicationPage)에도 영향이
 * 가므로, 가족 화면 전용으로 완전히 새로 분리했다(2026-07-21). */
export default function FamilyOcrProgressBar({ status, label }: FamilyOcrProgressBarProps) {
  const [percent, setPercent] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isActive = status === "pending" || status === "uploading" || status === "processing";
  const stage = useOcrStage(isActive);

  useEffect(() => {
    if (isActive) {
      setPercent((p) => (p <= 0 ? 4 : p));
      timerRef.current = setInterval(() => {
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
      if (timerRef.current) clearInterval(timerRef.current);
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
        @keyframes family-ocr-pill-bounce {
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
        {/* 알약 아이콘 - 진행률(percent)을 따라 가로로 이동(transition), 이동하는 동안
            위아래로 통통 튀는 연출은 별도 keyframe 애니메이션으로 분리해서 transform 속성이
            서로 안 겹치게 했다. */}
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
              animation: isActive ? "family-ocr-pill-bounce 0.6s ease-in-out infinite" : "none",
            }}
          >
            💊
          </span>
        </div>
      </div>
    </div>
  );
}
