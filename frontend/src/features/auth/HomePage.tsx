// src/features/auth/HomePage.tsx
// [starter] 로그인 성공 확인용 최소 화면입니다. 다른 도메인 화면이 생기면
// 이 페이지는 대시보드 등으로 교체하고, 로그아웃 버튼만 공용 레이아웃으로 옮기면 됩니다.
import { useAuthStore } from "../../store/authStore";
import { authApi } from "../../api/endpoints/auth";

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } finally {
      logout();
      window.location.href = "/login";
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <h1>로그인 성공</h1>
      {user ? (
        <p>
          {user.name}({user.email}) 님 환영합니다.
        </p>
      ) : (
        <p>사용자 정보를 불러오는 중이거나, /users/me 연동 전입니다.</p>
      )}
      <button onClick={handleLogout}>로그아웃</button>
    </div>
  );
}
