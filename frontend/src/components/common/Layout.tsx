import { useNavigate, Outlet } from "react-router-dom";

import { pinkTheme } from "../../theme/pinkTheme";

import BottomNav from "./BottomNav";
import InstallPwaBanner from "./InstallPwaBanner";

/** 앱 화면 공통 뼈대(2026-07-18) - 상단은 "더보기"로 바로 가는 햄버거 아이콘 하나만 두고,
 * 자주 쓰는 화면은 하단 아이콘 탭 바(BottomNav) + 더보기 화면 그리드로 접근한다. 예전 상단
 * 텍스트 탭(트랙커/상담/정보/복약알림)이 가리키던 화면들은 모두 홈 화면 바로가기 아이콘이나
 * 더보기/하단바에서 여전히 갈 수 있어 끊기는 화면이 없다. "뒤로가기"는 여기(전역 바)가 아니라
 * 더보기 화면 안에(다른 화면들과 같은 스타일로) 따로 있다 - MorePage.tsx 참고. */
export default function Layout() {
  const navigate = useNavigate();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <nav
        style={{
          display: "flex",
          justifyContent: "flex-end",
          padding: "8px 12px",
          borderBottom: `1px solid ${pinkTheme.border}`,
          background: pinkTheme.cardBg,
          alignItems: "center",
        }}
      >
        <button
          type="button"
          aria-label="더보기 메뉴 열기"
          onClick={() => navigate("/more")}
          style={{
            border: "none",
            background: "none",
            color: pinkTheme.text,
            fontSize: 20,
            lineHeight: 1,
            padding: 4,
            cursor: "pointer",
          }}
        >
          ☰
        </button>
      </nav>
      {/* 선택 기능(설치 안 해도 무방) - 설치 가능/미설치 상태일 때만 뜨고, 닫으면 이
          기기에서는 다시 안 뜬다. */}
      <InstallPwaBanner />
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
