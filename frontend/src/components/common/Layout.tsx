import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

/** 5탭(홈/트랙커/상담/정보/더보기) 공통 뼈대. 스타일은 최소한(FRONTEND_ARCHITECTURE.md 5번 — 톤 정해지기 전) */
export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div>
      <nav style={{ display: "flex", gap: "12px", padding: "8px 12px", borderBottom: "1px solid #ccc" }}>
        <Link to="/">홈</Link>
        <Link to="/track">트랙커</Link>
        <Link to="/chat">상담</Link>
        <Link to="/info">정보</Link>
        <Link to="/more">더보기</Link>
        <span style={{ marginLeft: "auto" }}>
          {user?.name}님{" "}
          <Link to="/account-settings">계정 설정</Link>{" "}
          <button type="button" onClick={logout}>
            로그아웃
          </button>
        </span>
      </nav>
      <Outlet />
    </div>
  );
}
