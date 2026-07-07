import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { authApi } from "../api/authApi";
import { setAccessToken } from "../api/client";
import type { SocialSignupCompletePayload, UserInfoResult } from "../api/types";
interface AuthContextValue {
  user: UserInfoResult | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  completeSocialSignup: (provider: string, payload: SocialSignupCompletePayload) => Promise<void>;
  logout: () => void;
}
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfoResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const hasInitialized = useRef(false);
  const fetchMe = useCallback(async () => { setUser(await authApi.me()); }, []);
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;
    (async () => {
      try {
        const { access_token } = await authApi.refresh();
        setAccessToken(access_token);
        await fetchMe();
      } catch { setAccessToken(null); } finally { setIsLoading(false); }
    })();
  }, [fetchMe]);
  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authApi.login(email, password);
    setAccessToken(access_token);
    await fetchMe();
  }, [fetchMe]);
  const completeSocialSignup = useCallback(async (provider: string, payload: SocialSignupCompletePayload) => {
    const { access_token } = await authApi.completeSocialSignup(provider, payload);
    setAccessToken(access_token);
    await fetchMe();
  }, [fetchMe]);
  const logout = useCallback(() => { setAccessToken(null); setUser(null); }, []);
  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: user !== null, isLoading, login, completeSocialSignup, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth는 AuthProvider 안에서만 쓸 수 있다");
  return ctx;
}