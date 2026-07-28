/**
 * 인증 상태 공유 훅 + Provider — 로그인 여부/유저 정보만 전역 공유 (FRONTEND_ARCHITECTURE.md 6번 공통모듈).
 * 전역 상태 라이브러리는 도입하지 않고 Context 1개로 최소화하는 팀 방침에 따른다.
 *
 * 여기서 다루는 건 "클라이언트(세션) 상태"뿐이다 — 로그인 여부/토큰/내 계정정보.
 * "생활정보 입력했는지" 같은 도메인 사실은 서버(DB)가 원본이라 여기 캐싱하지 않는다 —
 * 그 도메인 화면이 직접 백엔드에 물어봐서 받은 값을 그대로 쓴다.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { authApi } from "../api/authApi";
import { setAccessToken, tryRefreshAccessToken } from "../api/client";
import type { UserInfoResult } from "../api/types";
import { clearDismissalForNewLogin } from "../utils/healthBannerDismiss";

interface AuthContextValue {
  user: UserInfoResult | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<UserInfoResult>;
  logout: () => Promise<void>;
  // (2026-07-28) 동의 화면에서 서버에 동의 시각을 저장한 뒤, 캐시된 user를 새로 안
  // 불러오면 Layout/RequireAuth가 여전히 "미동의"로 판단해 홈으로 못 넘어가고 다시
  // 동의화면으로 튕기는 버그가 있었다 - ConsentPage가 저장 직후 이걸 호출해서 캐시를
  // 갱신한다.
  refreshUser: () => Promise<UserInfoResult>;
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
    const me = await authApi.me();
    setUser(me);
    return me;
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
      const me = await fetchMe();
      // 탭을 안 닫고 로그아웃 후 재로그인하는 경우에도 건강정보 배너를 다시 물어보게 한다.
      clearDismissalForNewLogin(me.profile_id);
      return me;
    },
    [fetchMe],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // 로그아웃은 백엔드 호출이 실패해도(네트워크 문제 등) 로컬 상태는 정리해야 한다 -
      // 사용자 입장에서 "로그아웃이 안 됐다"고 느끼는 게 제일 나쁜 경험이다.
    }
    setAccessToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        logout,
        refreshUser: fetchMe,
      }}
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
