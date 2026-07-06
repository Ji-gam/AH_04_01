import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function DrugFoodInteractionPage() {
  return (
    <PlaceholderPage
      title="약물-음식 상호작용 경고"
      apiFile="src/api/endpoints/drugFoodInteraction.ts"
      note="analyze()는 아직 실제 LLM이 아니라 규칙 텍스트를 이어붙이기만 합니다."
    />
  );
}
