import { apiFetch, apiFetchRaw } from "./client";
import type {
  ChatMessageChunk,
  ChatMessageResponse,
  ChatSessionCreateResult,
  ChatSessionResponse,
} from "./types";

// text/plain 스트림을 줄 단위로 읽어 ChatMessageChunk로 파싱한다. api_spec_core_v1.yaml 참고.
async function* readChunks(res: Response): AsyncGenerator<ChatMessageChunk> {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) yield JSON.parse(line) as ChatMessageChunk;
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer) as ChatMessageChunk;
}

export const chatApi = {
  createSession: () => apiFetch<ChatSessionCreateResult>("/chat/sessions", { method: "POST" }),

  listSessions: () => apiFetch<ChatSessionResponse[]>("/chat/sessions"),

  listMessages: (sessionId: string) =>
    apiFetch<ChatMessageResponse[]>(`/chat/sessions/${sessionId}/messages`),

  sendMessage: async function* (
    sessionId: string,
    message: string,
  ): AsyncGenerator<ChatMessageChunk> {
    const res = await apiFetchRaw(`/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    yield* readChunks(res);
  },

  // T-LLM-2-langfuse-user-feedback: 204 No Content라 apiFetch(res.json())를 쓰면
  // 파싱 에러가 나서 raw fetch를 쓴다. 같은 메시지에 다시 보내면 서버가 값을 갱신한다(upsert).
  submitFeedback: async (messageId: number, value: "up" | "down", comment?: string) => {
    await apiFetchRaw(`/chat/messages/${messageId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ value, comment }),
    });
  },
};
