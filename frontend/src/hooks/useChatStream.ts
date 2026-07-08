/**
 * T-LLM-2 스트리밍 훅 — `docs/CODING_RULES.md` 3번(프론트엔드 규칙) 참고.
 */
import { useRef, useState } from "react";

import { chatApi } from "../api/chatApi";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  disclaimer?: string;
}

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  async function ensureSession(): Promise<string> {
    if (sessionIdRef.current) return sessionIdRef.current;
    const { session_id } = await chatApi.createSession();
    sessionIdRef.current = session_id;
    return session_id;
  }

  async function sendMessage(text: string) {
    if (!text.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setIsStreaming(true);

    try {
      const sessionId = await ensureSession();
      // React StrictMode가 setState 업데이터를 2번 호출해 순수성을 검증하므로,
      // 업데이터 내부에서 이 플래그를 직접 mutate하지 않는다(mutate하면 StrictMode에서
      // 토큰이 중복/누락된다) — 값은 for-await 루프 본문(업데이터 바깥)에서만 갱신한다.
      let assistantStarted = false;

      for await (const chunk of chatApi.sendMessage(sessionId, text)) {
        if (chunk.type === "token") {
          const isFirstToken = !assistantStarted;
          assistantStarted = true;
          setMessages((prev) => {
            if (isFirstToken) {
              return [...prev, { role: "assistant", content: chunk.content }];
            }
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + chunk.content };
            return next;
          });
        } else if (chunk.type === "emergency_fallback") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: chunk.content, disclaimer: chunk.disclaimer },
          ]);
        } else if (chunk.type === "done") {
          const hasAssistantMessage = assistantStarted;
          setMessages((prev) => {
            if (!hasAssistantMessage) return prev;
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, disclaimer: chunk.disclaimer };
            return next;
          });
        }
      }
    } catch (error) {
      console.error("채팅 메시지 전송 실패:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "메시지 전송에 실패했습니다. 잠시 후 다시 시도해주세요." },
      ]);
    } finally {
      setIsStreaming(false);
    }
  }

  return { messages, sendMessage, isStreaming };
}
