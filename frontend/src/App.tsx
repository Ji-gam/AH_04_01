// src/App.tsx
import { useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import { router } from "./routes/router";
import { useAuthStore } from "./store/authStore";
import { authApi } from "./api/endpoints/auth";

function App() {
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const setUser = useAuthStore((s) => s.setUser);
  const setAuthReady = useAuthStore((s) => s.setAuthReady);

  useEffect(() => {
    // 새로고침 시 메모리의 access_token은 사라지므로,
    // refresh_token 쿠키가 살아있으면 조용히 새 access_token을 받아옵니다.
    (async () => {
      try {
        const { access_token } = await authApi.refresh();
        setAccessToken(access_token);
        try {
          const me = await authApi.getMe();
          setUser(me);
        } catch {
          // /users/me 연동 전이어도 로그인 세션 자체는 유지
        }
      } catch {
        // 쿠키 없거나 만료 -> 로그인 필요 (정상 상황)
      } finally {
        setAuthReady(true);
      }
    })();
  }, [setAccessToken, setUser, setAuthReady]);

  return <RouterProvider router={router} />;
}

export default App;
