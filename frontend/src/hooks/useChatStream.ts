/**
 * T-LLM-2 스트리밍 훅. 소유자: 서현(RAG/Chat 연동) — FRONTEND_ARCHITECTURE.md 6번.
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
      let assistantStarted = false;

      for await (const chunk of chatApi.sendMessage(sessionId, text)) {
        if (chunk.type === "token") {
          setMessages((prev) => {
            if (!assistantStarted) {
              assistantStarted = true;
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
          setMessages((prev) => {
            if (!assistantStarted) return prev;
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
