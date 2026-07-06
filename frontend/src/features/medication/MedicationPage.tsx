import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function MedicationPage() {
  return (
    <PlaceholderPage
      title="의약품 정보 / 알약 검색"
      apiFile="src/api/endpoints/medication.ts"
      note="알약 이미지 검색은 pgvector 도입 전까지 항상 빈 결과만 반환합니다 (보류 상태)."
    />
  );
}
