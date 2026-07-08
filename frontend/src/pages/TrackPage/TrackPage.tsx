export default function TrackPage() {
  return (
    <div style={{ padding: "20px" }}>
      <h1>트랙커</h1>
      <div style={{ border: "1px solid #ccc", padding: "15px", margin: "15px 0" }}>
        <h3>복약 관리</h3>
        <p>처방전/알약을 스캔하여 복약 일정을 자동으로 스케줄링하고 관리할 수 있습니다.</p>
        <button onClick={() => window.location.href = "/medication"} style={{ padding: "8px 16px", cursor: "pointer" }}>
          복약 스케줄 & 처방전 OCR 관리 바로가기
        </button>
      </div>
      {/* 복약관리를 포함한 단일 스크롤(하위 탭으로 안 쪼갠다). 콘텐츠가 있을 때만 섹션 노출 — FRONTEND_ARCHITECTURE.md 참고 */}
      {/* <AdherenceHeatmapSection /> */}
      {/* <LifestyleSurveySection /> */}
      {/* <DietTrackingSection /> */}
      {/* <HealthAppSyncSection /> */}
    </div>
  );
}
