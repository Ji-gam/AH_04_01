import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

import BottomNav from "./BottomNav";

// 모든 탭 링크를 복약알림과 같은 톤(핑크·볼드)으로 통일한다.
const navLinkStyle: React.CSSProperties = {
  color: pinkTheme.primary,
  fontWeight: 600,
  textDecoration: "none",
};

/** 5탭(홈/트랙커/상담/정보/더보기) 공통 뼈대. 홈은 비로그인도 접근 가능해서, 로그인 여부에 따라
 * 우측 상단 영역이 "로그인" 버튼이거나 "이름님 + 개인정보수정 + 로그아웃"으로 갈린다. */
export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/", { replace: true });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <nav
        style={{
          display: "flex",
          gap: "12px",
          padding: "8px 12px",
          borderBottom: `1px solid ${pinkTheme.border}`,
          background: pinkTheme.cardBg,
          alignItems: "center",
        }}
      >
        <Link to="/" style={navLinkStyle}>
          홈
        </Link>
        <Link to="/track" style={navLinkStyle}>
          트랙커
        </Link>
        <Link to="/chat" style={navLinkStyle}>
          상담
        </Link>
        <Link to="/info" style={navLinkStyle}>
          정보
        </Link>
        <Link to="/alarms" style={navLinkStyle}>
          복약알림
        </Link>
        <Link to="/more" style={navLinkStyle}>
          더보기
        </Link>
        <span
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13,
            color: pinkTheme.text,
          }}
        >
          {user ? (
            <>
              {user.name}님{" "}
              <Link to="/account-settings" style={{ color: pinkTheme.textMuted, fontSize: 12 }}>
                개인정보수정
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                style={{
                  border: `1px solid ${pinkTheme.border}`,
                  borderRadius: 8,
                  background: pinkTheme.cardBg,
                  color: pinkTheme.textMuted,
                  fontSize: 12,
                  padding: "4px 10px",
                  cursor: "pointer",
                }}
              >
                로그아웃
              </button>
            </>
          ) : (
            <Link to="/login" style={navLinkStyle}>
              로그인
            </Link>
          )}
        </span>
      </nav>
      {/* nav 높이를 뺀 나머지 전체를 자식(Outlet)에 넘긴다 — 자식이 height:100dvh를 다시
          쓰면 nav 높이만큼 화면 아래로 넘쳐서 폼 같은 하단 요소가 잘려 보이지 않는다. */}
      <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        <Outlet />
      </div>
      {/* 앱 패키징을 대비한 하단 아이콘 탭 바 - 모든 화면에서 항상 보인다. */}
      <BottomNav />
    </div>
  );
}
