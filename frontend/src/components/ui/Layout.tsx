// src/components/ui/Layout.tsx
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { authApi } from "../../api/endpoints/auth";

const NAV_ITEMS = [
  { to: "/schedules", label: "복약 스케줄" },
  { to: "/records", label: "진료 기록" },
  { to: "/medications", label: "의약품 정보" },
  { to: "/intake-logs", label: "복약 이력" },
  { to: "/food-intake", label: "식사 기록" },
  { to: "/drug-food-interactions", label: "약물-음식 상호작용" },
  { to: "/health-metrics", label: "건강 지표" },
  { to: "/appointments", label: "병원 예약" },
  { to: "/symptom-logs", label: "증상 기록" },
  { to: "/emergency-card", label: "응급 의료 카드" },
  { to: "/support-group", label: "서포트 그룹" },
  { to: "/pwa-subscription", label: "푸시 알림" },
  { to: "/chat", label: "AI 상담" },
  { to: "/generated-guides", label: "AI 맞춤 가이드" },
];

export default function Layout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      logout();
      navigate("/login");
    }
  };

  return (
    <div className="flex min-h-screen">
      <aside
        className="flex w-64 flex-col border-r p-4"
        style={{ borderColor: "var(--panel-border)", background: "var(--panel-bg)" }}
      >
        <div className="mb-6">
          <h2 className="text-lg font-bold">ReMedi</h2>
          {user && <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{user.name}님</p>}
        </div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? "font-semibold" : ""}`
              }
              style={({ isActive }) => ({
                background: isActive ? "rgba(0,242,254,0.12)" : "transparent",
                color: isActive ? "var(--accent-cyan)" : "var(--text-secondary)",
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={handleLogout}
          className="mt-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
          style={{ color: "var(--text-secondary)" }}
        >
          <LogOut size={16} /> 로그아웃
        </button>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
