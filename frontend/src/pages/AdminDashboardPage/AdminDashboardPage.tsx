import { Link } from "react-router-dom";

/** T-ADMIN-1: 관리자 홈. 아무도 안 보는 화면이라 스타일링 없이 링크만 둔다. */
export default function AdminDashboardPage() {
  return (
    <div style={{ padding: 16 }}>
      <h1>관리자</h1>
      <ul>
        <li>
          <Link to="/admin/chat">채팅 모니터링</Link>
        </li>
        <li>
          <Link to="/admin/rag">RAG 소스 인제스트</Link>
        </li>
      </ul>
    </div>
  );
}
