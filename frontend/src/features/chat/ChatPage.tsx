import PlaceholderPage from "../../components/ui/PlaceholderPage";
export default function ChatPage() {
  return (
    <PlaceholderPage
      title="AI 상담 챗봇"
      apiFile="src/api/endpoints/chat.ts"
      note="백엔드가 아직 SSE 스트리밍이 아니라 일반 JSON 응답이라, 실시간 타이핑 효과는 없습니다."
    />
  );
}
