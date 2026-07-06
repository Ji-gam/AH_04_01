// src/api/endpoints/chat.ts
import { apiClient } from "../client";
import type { ChatSession, ChatMessage } from "../../types";

export const chatApi = {
  listSessions: async (): Promise<ChatSession[]> => {
    const res = await apiClient.get("/chat/sessions");
    return res.data;
  },
  createSession: async (sessionTitle: string, intentMode: "DIET_ASSIST" | "PARENT_MONITOR") => {
    const res = await apiClient.post("/chat/sessions", {
      session_title: sessionTitle,
      session_intent_mode: intentMode,
      has_injected_context: true,
    });
    return res.data as ChatSession;
  },
  // ⚠️ [단순화] 백엔드가 아직 SSE 스트리밍이 아니라 일반 JSON 응답입니다.
  // 나중에 SSE로 바뀌면 이 함수를 EventSource 기반으로 교체해야 합니다.
  sendMessage: async (sessionId: number, content: string): Promise<ChatMessage> => {
    const res = await apiClient.post(`/chat/sessions/${sessionId}/messages`, { content });
    return res.data;
  },
};
