import { NavLink } from "react-router-dom";

import { pinkTheme } from "../../theme/pinkTheme";

const NAV_ITEMS = [
  { to: "/alarms", icon: "📅", label: "복약스케줄" },
  { to: "/medication", icon: "➕", label: "약등록" },
  { to: "/", icon: "🏠", label: "홈" },
  { to: "/family", icon: "👨‍👩‍👧", label: "가족관리" },
  { to: "/emergency-guide", icon: "🚨", label: "응급안내" },
];

/** 앱 패키징을 대비한 하단 아이콘 탭 바(피그마 시안 반영, 2026-07-16). 기존 상단 텍스트
 * 네비게이션(Layout.tsx)은 그대로 두고, 자주 쓰는 5개 화면만 하단에 추가로 노출한다.
 * Layout의 flex 자식으로 배치되어 있어(fixed/sticky 아님) 어떤 화면에서도 항상 보인다. */
export default function BottomNav() {
  return (
    <nav
      style={{
        display: "flex",
        flexShrink: 0,
        borderTop: `1px solid ${pinkTheme.border}`,
        background: pinkTheme.cardBg,
        padding: "6px 0",
      }}
    >
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end
          style={({ isActive }) => ({
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 2,
            padding: "4px 0",
            textDecoration: "none",
            color: isActive ? pinkTheme.primary : pinkTheme.textMuted,
            fontWeight: isActive ? 700 : 500,
          })}
        >
          <span style={{ fontSize: 20 }} aria-hidden>
            {item.icon}
          </span>
          <span style={{ fontSize: 11 }}>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
