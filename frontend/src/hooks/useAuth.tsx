/**
 * 인증 상태 공유 훅 + Provider — 로그인 여부/유저 정보만 전역 공유 (FRONTEND_ARCHITECTURE.md 6번 공통모듈).
 * 전역 상태 라이브러리는 도입하지 않고 Context 1개로 최소화하는 팀 방침에 따른다.
 *
 * 여기서 다루는 건 "클라이언트(세션) 상태"뿐이다 — 로그인 여부/토큰/내 계정정보.
 * "생활정보 입력했는지" 같은 도메인 사실은 서버(DB)가 원본이라 여기 캐싱하지 않는다 —
 * 그 도메인 화면이 직접 백엔드에 물어봐서 받은 값을 그대로 쓴다.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { authApi } from "../api/authApi";
import { setAccessToken, tryRefreshAccessToken } from "../api/client";
import type { UserInfoResult } from "../api/types";

interface AuthContextValue {
  user: UserInfoResult | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfoResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // React 18 StrictMode(개발모드)가 마운트 effect를 일부러 두 번 실행하는데, 그때마다
  // /auth/token/refresh를 따로 호출하면 리프레시 토큰 로테이션 로직이 "같은 토큰이 거의
  // 동시에 두 번 쓰였다"고 오인해서 재사용(탈취)으로 착각해 전체 세션을 무효화해버린다.
  // 이 ref로 실제 요청은 한 번만 나가게 막는다.
  const didInit = useRef(false);

  const fetchMe = useCallback(async () => {
    setUser(await authApi.me());
  }, []);

  useEffect(() => {
  if (didInit.current) return;
  didInit.current = true;

  (async () => {
    try {
      const ok = await tryRefreshAccessToken();
      if (ok) {
        await fetchMe();
      }
    } finally {
      setIsLoading(false);
    }
  })();
}, [fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await authApi.login(email, password);
      setAccessToken(access_token);
      await fetchMe();
    },
    [fetchMe],
  );

  const logout = useCallback(() => {
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: user !== null, isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- Provider+훅을 한 파일에 두는 게 팀 문서(FRONTEND_ARCHITECTURE.md)의 지정 위치다
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth는 AuthProvider 안에서만 쓸 수 있다");
  }
  return ctx;
}
