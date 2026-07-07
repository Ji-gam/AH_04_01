import { apiFetch, apiFetchRaw } from "./client";
import type { ChatMessageChunk, ChatSessionCreateResult } from "./types";

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
};
