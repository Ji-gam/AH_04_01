/**
 * T-LLM-2 스트리밍 훅 — `docs/CODING_RULES.md` 3번(프론트엔드 규칙) 참고.
 */
import { useEffect, useState } from "react";

import { chatApi } from "../api/chatApi";
import type { ChatSessionResponse, ChatSourceRef } from "../api/types";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  disclaimer?: string;
  sources?: ChatSourceRef[];
}

interface Options {
  /** 홈 화면 "AI 건강 상담" 입력창에서 넘어와 바로 새 질문을 보낼 예정이면 true로 넘긴다.
   * 마운트 시 "마지막 상담 복원"을 건너뛰어, 복원 응답이 뒤늦게 도착해 방금 낙관적으로
   * 추가한 사용자 질문을 덮어써버리는 경쟁 상태(race condition)를 막는다. */
  skipRestoreOnMount?: boolean;
}

export function useChatStream(options: Options = {}) {
  const { skipRestoreOnMount = false } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionList, setSessionList] = useState<ChatSessionResponse[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const loadSessions = async () => {
    try {
      const list = await chatApi.listSessions();
      setSessionList(list);
      return list;
    } catch (err) {
      console.error("세션 목록 로드 실패:", err);
      return [];
    }
  };

  const selectSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsStreaming(false);
    try {
      const history = await chatApi.listMessages(sessionId);
      // 기존 메시지는 생성 시각 순서대로 정렬되어 반환됨
      setMessages(history.map((m) => ({ role: m.role, content: m.content })));
    } catch (err) {
      console.error("이전 대화 로드 실패:", err);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setCurrentSessionId(null);
  };

  // 컴포넌트 마운트 시 세션 목록을 조회하고, 마지막 세션이 있다면 복원합니다.
  // (skipRestoreOnMount가 true면 목록만 불러오고 복원은 건너뛴다 - 상단 옵션 설명 참고)
  useEffect(() => {
    void (async () => {
      const list = await loadSessions();
      if (!skipRestoreOnMount && list.length > 0) {
        // 가장 최근 세션 ID 로드
        const latestSessionId = String(list[0].id);
        void selectSession(latestSessionId);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ensureSession(): Promise<string> {
    if (currentSessionId) return currentSessionId;
    const { session_id } = await chatApi.createSession();
    setCurrentSessionId(session_id);
    void loadSessions(); // 새로운 세션이 생겼으므로 목록을 갱신합니다.
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
        } else if (chunk.type === "paper_answer") {
          // 논문 검색 답변은 paper_agent가 이미 완성해서 보내주므로 토큰 스트리밍 없이
          // 한 번에 추가한다("assistantStarted"를 켜서 뒤이어 올 done의 disclaimer 갱신 대상이 되게 함).
          assistantStarted = true;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: chunk.content, sources: chunk.sources },
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

  return {
    messages,
    sendMessage,
    isStreaming,
    sessionList,
    currentSessionId,
    selectSession,
    startNewChat,
    loadSessions,
  };
}
