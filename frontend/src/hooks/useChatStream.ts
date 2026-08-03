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
  // T-LLM-2-langfuse-user-feedback: 어시스턴트 메시지에만 채워진다("done" 청크 또는
  // 이력 조회 응답에서). 피드백 API가 이 값으로 대상을 지정한다 - Langfuse trace_id는
  // 서버 내부 식별자라 여기 노출되지 않는다(설계 결정 1).
  messageId?: number;
  feedback?: "up" | "down";
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
      // 기존 메시지는 생성 시각 순서대로 정렬되어 반환됨. sources/disclaimer는 어시스턴트
      // 메시지에만 저장되어 있으며(T-LLM-7-3-2), 없으면 undefined로 둬 칩/면책문구를 렌더링하지 않는다.
      setMessages(
        history.map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources ?? undefined,
          disclaimer: m.disclaimer ?? undefined,
          messageId: m.id,
        })),
      );
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
    return session_id;
  }

  async function sendMessage(text: string) {
    if (!text.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setIsStreaming(true);

    try {
      const sessionId = await ensureSession();

      // T-LLM-7-3-2: 통합 RAG 스트리밍 프로토콜은 매 답변마다 "sources"가 먼저 도착해
      // 새 어시스턴트 메시지를 열고(DUR+논문 출처가 합쳐진 목록, 없으면 빈 배열), 그
      // 다음 "token"이 그 메시지에 이어붙는다 — emergency_fallback만 예외로 sources 없이
      // 단독 메시지를 만든다.
      for await (const chunk of chatApi.sendMessage(sessionId, text)) {
        if (chunk.type === "sources") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "", sources: chunk.sources },
          ]);
        } else if (chunk.type === "token") {
          setMessages((prev) => {
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
            const next = [...prev];
            const last = next[next.length - 1];
            next[next.length - 1] = {
              ...last,
              disclaimer: chunk.disclaimer,
              messageId: chunk.message_id,
            };
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
      // 세션 목록은 "마지막 대화일" 기준 최신순이라(app/repositories/chat_repository.py),
      // 기존 세션에 메시지를 이어 보낼 때마다(ensureSession이 새 세션일 때만 갱신하므로
      // 여기선 빠짐) 다시 불러와야 방금 대화한 세션이 목록 맨 위로 올라온다.
      void loadSessions();
    }
  }

  // T-LLM-2-langfuse-user-feedback: 👍/👎 - 낙관적으로 먼저 반영하고, 전송 실패 시에만
  // 되돌린다(사용자가 누른 즉시 피드백을 보여주는 게 중요하고, 실패는 드물기 때문).
  async function sendFeedback(index: number, value: "up" | "down") {
    const target = messages[index];
    if (!target?.messageId) return;
    const previousFeedback = target.feedback;

    setMessages((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], feedback: value };
      return next;
    });

    try {
      await chatApi.submitFeedback(target.messageId, value);
    } catch (err) {
      console.error("피드백 전송 실패:", err);
      setMessages((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], feedback: previousFeedback };
        return next;
      });
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
    sendFeedback,
  };
}
