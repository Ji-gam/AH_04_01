// src/routes/ProtectedRoute.tsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export default function ProtectedRoute() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const isAuthReady = useAuthStore((s) => s.isAuthReady);

  // 앱 시작 시 refresh 시도가 아직 안 끝났으면 잠깐 대기 (깜빡이며 로그인 화면으로 튕기는 것 방지)
  if (!isAuthReady) {
    return <div className="p-6" style={{ color: "var(--text-secondary)" }}>불러오는 중...</div>;
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
