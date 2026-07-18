import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { adminApi } from "../../api/adminApi";
import type { AdminChatSessionListItem } from "../../api/types";

/** T-ADMIN-1: 전체 프로필의 채팅 세션 목록. 관리자 전용, 스타일링 없음. */
export default function AdminChatSessionsPage() {
  const [sessions, setSessions] = useState<AdminChatSessionListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminApi
      .listChatSessions()
      .then(setSessions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) return <p style={{ padding: 16 }}>로딩 중...</p>;
  if (error) return <p style={{ padding: 16 }}>에러: {error}</p>;

  return (
    <div style={{ padding: 16 }}>
      <h1>채팅 세션 목록</h1>
      <table border={1} cellPadding={6}>
        <thead>
          <tr>
            <th>세션 ID</th>
            <th>프로필</th>
            <th>생성 시각</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id}>
              <td>
                <Link to={`/admin/chat/${s.id}`}>{s.id}</Link>
              </td>
              <td>
                {s.profile_name} (#{s.profile_id})
              </td>
              <td>{s.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
