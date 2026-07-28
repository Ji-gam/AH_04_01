import { useNavigate, useLocation, Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";
import { pinkTheme } from "../../theme/pinkTheme";

import BottomNav from "./BottomNav";
import InstallPwaBanner from "./InstallPwaBanner";
import NotificationBell from "./NotificationBell";

/** 앱 화면 공통 뼈대(2026-07-18) - 상단은 "더보기"로 바로 가는 햄버거 아이콘 하나만 두고,
 * 자주 쓰는 화면은 하단 아이콘 탭 바(BottomNav) + 더보기 화면 그리드로 접근한다. 예전 상단
 * 텍스트 탭(트랙커/상담/정보/복약알림)이 가리키던 화면들은 모두 홈 화면 바로가기 아이콘이나
 * 더보기/하단바에서 여전히 갈 수 있어 끊기는 화면이 없다. "뒤로가기"는 여기(전역 바)가 아니라
 * 더보기 화면 안에(다른 화면들과 같은 스타일로) 따로 있다 - MorePage.tsx 참고.
 * 햄버거 왼쪽엔 🔔 알림함(NotificationBell, 2026-07-26)을 둔다 - 복약알림/공지/가족알림/
 * 리포트 등 발송된 알림을 어느 화면에서든 바로 열어볼 수 있게 한다.
 *
 * [2026-07-28 버그 수정] 통합 동의 게이트를 RequireAuth + LoginPage에만 넣어뒀는데,
 * 소셜로그인은 그 두 곳을 아예 안 거치고 백엔드 콜백이 바로 "/"로 리다이렉트한다 -
 * 그리고 "/"를 비롯한 대부분의 탭은 RequireAuth로 안 감싸져 있어(비로그인도 볼 수
 * 있어야 해서) 소셜로그인 사용자가 동의 화면을 아예 안 보고 그냥 들어와버렸다. 이
 * Layout이 거의 모든 라우트를 감싸는 공통 지점이라 여기서 한 번 더 확인한다 -
 * 비로그인 사용자는 그대로 두고(로그인 자체를 강제하지 않음), 로그인은 했는데
 * 필수 동의가 안 끝난 경우만 걸러낸다. */
export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated } = useAuth();

  const consentDone =
    !!user?.terms_of_service_consented_at && !!user?.health_info_consented_at && !!user?.ai_chat_consented_at;
  if (isAuthenticated && !consentDone && location.pathname !== "/health-info/consent") {
    return <Navigate to="/health-info/consent" replace state={{ from: location.pathname }} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100dvh" }}>
      <nav
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "8px 12px",
          borderBottom: `1px solid ${pinkTheme.border}`,
          background: pinkTheme.cardBg,
          alignItems: "center",
        }}
      >
        <button
          type="button"
          aria-label="홈으로 이동"
          onClick={() => navigate("/")}
          style={{
            border: "none",
            background: "none",
            padding: 0,
            cursor: "pointer",
            lineHeight: 0,
          }}
        >
          <img
            src="/icons/icon-192.png"
            alt=""
            width={36}
            height={36}
            style={{ borderRadius: 8 }}
          />
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <NotificationBell />
          <button
            type="button"
            aria-label="더보기 메뉴 열기"
            onClick={() => navigate("/more")}
            style={{
              width: 36,
              height: 36,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "none",
              background: "none",
              color: pinkTheme.text,
              fontSize: 22,
              lineHeight: 1,
              padding: 0,
              cursor: "pointer",
            }}
          >
            ☰
          </button>
        </div>
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
