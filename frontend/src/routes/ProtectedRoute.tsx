// src/routes/ProtectedRoute.tsx
// [starter] 공유 구역(routes/)입니다.
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export default function ProtectedRoute() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const isAuthReady = useAuthStore((s) => s.isAuthReady);

  if (!isAuthReady) {
    return <div style={{ padding: 24 }}>불러오는 중...</div>;
  }

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
