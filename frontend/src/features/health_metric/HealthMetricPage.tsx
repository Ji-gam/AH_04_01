import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function HealthMetricPage() {
  return (
    <PlaceholderPage
      title="건강 지표 (체중/혈압/혈당)"
      apiFile="src/api/endpoints/healthMetric.ts"
      note="목록 조회 API가 백엔드에 아직 없어서, 추이 그래프를 만들려면 백엔드에 GET부터 추가해야 합니다."
    />
  );
}
