import { useLocation, useNavigate } from "react-router-dom";

import { pinkTheme } from "../../theme/pinkTheme";

/** 더보기 > 처방전 등록에서 열었을 때만 뒤로가기가 더보기로 돌아간다(2026-07-16) - 상단
 * 네비게이션의 "트랙커" 탭으로 들어왔을 때는 홈으로 나간다. */
export default function TrackPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const cameFromMore = (location.state as { from?: string } | null)?.from === "more";

  return (
    <div style={{ background: pinkTheme.pageBg, minHeight: "100%", padding: "24px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>
        <button
          type="button"
          onClick={() => navigate(cameFromMore ? "/more" : "/")}
          style={{
            background: "none",
            border: "none",
            color: pinkTheme.textMuted,
            padding: 0,
            marginBottom: 10,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          ← 뒤로가기
        </button>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: pinkTheme.text, margin: "0 0 20px" }}>
          📊 트랙커
        </h1>

        <div
          style={{
            background: pinkTheme.cardBg,
            border: `1px solid ${pinkTheme.border}`,
            borderRadius: 16,
            padding: 18,
            marginBottom: 16,
            boxShadow: "0 2px 10px rgba(255, 111, 145, 0.1)",
          }}
        >
          <p style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 700, color: pinkTheme.primary }}>
            💊 복약 관리
          </p>
          <p
            style={{
              margin: "0 0 14px",
              fontSize: 13,
              color: pinkTheme.textMuted,
              lineHeight: 1.5,
            }}
          >
            처방전/알약을 스캔하여 복약 일정을 자동으로 스케줄링하고 관리할 수 있습니다.
          </p>
          <button
            type="button"
            onClick={() => navigate("/medication")}
            style={{
              width: "100%",
              padding: "12px 0",
              border: "none",
              borderRadius: 10,
              background: pinkTheme.primary,
              color: "#fff",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            복약 스케줄 & 처방전 OCR 관리 바로가기
          </button>
        </div>

        {/* 복약관리를 포함한 단일 스크롤(하위 탭으로 안 쪼갠다). 콘텐츠가 있을 때만 섹션 노출 — FRONTEND_ARCHITECTURE.md 참고 */}
        {/* <AdherenceHeatmapSection /> */}
        {/* <LifestyleSurveySection /> */}
        {/* <DietTrackingSection /> */}
        {/* <HealthAppSyncSection /> */}
      </div>
    </div>
  );
}
