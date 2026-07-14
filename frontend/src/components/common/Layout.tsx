import { Link, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

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
          borderBottom: "1px solid #ccc",
          alignItems: "center",
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
          {user ? (
            <>
              {user.name}님 <Link to="/account-settings">개인정보수정</Link>{" "}
              <button type="button" onClick={handleLogout}>
                로그아웃
              </button>
            </>
          ) : (
            <Link to="/login">로그인</Link>
          )}
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
