import { pinkTheme } from "../../theme/pinkTheme";

import OcrProgressBar, { type OcrJobStatus } from "./OcrProgressBar";

interface OcrFullscreenOverlayProps {
  status: OcrJobStatus | null;
  /** 지정하면 자동 단계 문구 대신 이 텍스트를 고정으로 보여준다. */
  label?: string;
}

/** OCR 분석 중에는 화면 전체를 덮어 다른 조작을 막고 진행 상태에 집중시킨다.
 * pending/uploading/processing이 아니면(=닫혀야 하면) 아무것도 렌더링하지 않는다. */
export default function OcrFullscreenOverlay({ status, label }: OcrFullscreenOverlayProps) {
  const isActive = status === "pending" || status === "uploading" || status === "processing";
  if (!isActive) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 2000,
        background: "rgba(90, 74, 78, 0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 360,
          background: pinkTheme.cardBg,
          borderRadius: 16,
          padding: "32px 24px",
          boxShadow: "0 12px 32px rgba(0, 0, 0, 0.18)",
        }}
      >
        <OcrProgressBar status={status} label={label} />
      </div>
    </div>
  );
}
