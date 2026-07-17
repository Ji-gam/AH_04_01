import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { adminApi } from "../../api/adminApi";
import type { ChatMessageResponse } from "../../api/types";

/** T-ADMIN-1: 세션 상세 - 메시지 + 출처(RAG score 포함) 조회. 관리자 전용, 스타일링 없음. */
export default function AdminChatSessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [messages, setMessages] = useState<ChatMessageResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    adminApi
      .getChatSessionMessages(Number(sessionId))
      .then(setMessages)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, [sessionId]);

  if (isLoading) return <p style={{ padding: 16 }}>로딩 중...</p>;
  if (error) return <p style={{ padding: 16 }}>에러: {error}</p>;

  return (
    <div style={{ padding: 16 }}>
      <h1>세션 #{sessionId} 메시지</h1>
      {messages.map((m, i) => (
        <div key={i} style={{ marginBottom: 12, borderBottom: "1px solid #ccc", paddingBottom: 8 }}>
          <strong>{m.role}</strong> ({m.created_at})<p>{m.content}</p>
          {m.sources && m.sources.length > 0 && (
            <ul>
              {m.sources.map((s, j) => (
                <li key={j}>
                  {s.name}
                  {s.url ? ` (${s.url})` : ""}
                  {s.score != null ? ` — score: ${s.score.toFixed(4)}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
