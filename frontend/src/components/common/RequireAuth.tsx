import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../../hooks/useAuth";

/** 로그인 안 했으면 /login으로 튕기는 가드. 5탭 라우트를 이걸로 감싼다. */
export default function RequireAuth() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <p>로딩 중...</p>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
