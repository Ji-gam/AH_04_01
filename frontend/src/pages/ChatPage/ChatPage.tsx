/**
 * '상담'(LLM상담) 탭 — T-LLM-2. 모바일웹(PWA) 우선 레이아웃 (decision_log.md 참고).
 * 스타일은 팀이 유틸리티 클래스를 확정하기 전까지 최소 inline style로 둔다 (FRONTEND_ARCHITECTURE.md 5번).
 */
import { useState } from "react";

import DisclaimerBanner from "../../components/common/DisclaimerBanner";
import { useChatStream } from "../../hooks/useChatStream";

export default function ChatPage() {
  const { messages, sendMessage, isStreaming } = useChatStream();
  const [input, setInput] = useState("");

  async function handleSend() {
    const text = input;
    setInput("");
    await sendMessage(text);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <h1>상담</h1>
      <DisclaimerBanner />

      <div style={{ flex: 1, overflowY: "auto", padding: "8px 12px" }}>
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.role === "user" ? "right" : "left", margin: "8px 0" }}>
            <p style={{ display: "inline-block", maxWidth: "85%", whiteSpace: "pre-wrap" }}>
              {m.content}
            </p>
          </div>
        ))}
        {isStreaming && <p role="status">답변 작성 중...</p>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
        style={{ display: "flex", gap: "8px", padding: "8px 12px" }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="궁금한 점을 물어보세요"
          disabled={isStreaming}
          style={{ flex: 1, padding: "10px", fontSize: "16px" }}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          style={{ padding: "10px 16px" }}
        >
          전송
        </button>
      </form>
    </div>
  );
}
