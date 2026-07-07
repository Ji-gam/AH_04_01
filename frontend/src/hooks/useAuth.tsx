/**
 * 인증 상태 공유 훅 + Provider — 로그인 여부/유저 정보만 전역 공유 (FRONTEND_ARCHITECTURE.md 6번 공통모듈).
 * 전역 상태 라이브러리는 도입하지 않고 Context 1개로 최소화하는 팀 방침에 따른다.
 *
 * 여기서 다루는 건 "클라이언트(세션) 상태"뿐이다 — 로그인 여부/토큰/내 계정정보.
 * "생활정보 입력했는지" 같은 도메인 사실은 서버(DB)가 원본이라 여기 캐싱하지 않는다 —
 * 그 도메인 화면이 직접 백엔드에 물어봐서 받은 값을 그대로 쓴다.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { authApi } from "../api/authApi";
import { setAccessToken } from "../api/client";
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

  const fetchMe = useCallback(async () => {
    setUser(await authApi.me());
  }, []);

  useEffect(() => {
    // 새로고침해도 로그인이 풀리지 않도록, httpOnly refresh_token 쿠키로 세션 복구를 시도한다.
    // 쿠키가 없거나 만료됐으면 그냥 비로그인 상태로 남는다(에러를 화면에 보여주지 않음).
    (async () => {
      try {
        const { access_token } = await authApi.refresh();
        setAccessToken(access_token);
        await fetchMe();
      } catch {
        setAccessToken(null);
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
    <AuthContext.Provider value={{ user, isAuthenticated: user !== null, isLoading, login, logout }}>
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
