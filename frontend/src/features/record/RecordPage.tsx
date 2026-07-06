import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function RecordPage() {
  return (
    <PlaceholderPage
      title="진료 기록 (OCR)"
      apiFile="src/api/endpoints/record.ts"
      note="백엔드 OCR이 아직 실제 CLOVA 연동 전 스텁이라, 인식 결과는 항상 고정 문구로 옵니다."
    />
  );
}
