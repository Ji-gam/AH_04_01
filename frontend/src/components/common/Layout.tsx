import { Link, Outlet } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

/** 5탭(홈/트랙커/상담/정보/더보기) 공통 뼈대. 스타일은 최소한(FRONTEND_ARCHITECTURE.md 5번 — 톤 정해지기 전) */
export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <nav
        style={{
          display: "flex",
          gap: "12px",
          padding: "8px 12px",
          borderBottom: "1px solid #ccc",
        }}
      >
        <Link to="/">홈</Link>
        <Link to="/track">트랙커</Link>
        <Link to="/chat">상담</Link>
        <Link to="/info">정보</Link>
        <Link to="/alarms" style={{ color: "#FF6F91", fontWeight: 600 }}>
          복약알림
        </Link>
        <Link to="/more">더보기</Link>
        <span style={{ marginLeft: "auto" }}>
          {user?.name}님 <Link to="/account-settings">개인정보수정</Link>{" "}
          <button type="button" onClick={logout}>
            로그아웃
          </button>
        </span>
      </nav>
      {/* nav 높이를 뺀 나머지 전체를 자식(Outlet)에 넘긴다 — 자식이 height:100dvh를 다시
          쓰면 nav 높이만큼 화면 아래로 넘쳐서 폼 같은 하단 요소가 잘려 보이지 않는다. */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <Outlet />
      </div>
    </div>
  );
}
