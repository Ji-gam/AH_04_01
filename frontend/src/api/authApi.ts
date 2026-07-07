import { apiFetch } from "./client";
import type { AuthTokenResult, SignupPayload, SocialSignupCompletePayload, UserInfoResult } from "./types";
export const authApi = {
  signup: (payload: SignupPayload) =>
    apiFetch<{ detail: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (email: string, password: string) =>
    apiFetch<AuthTokenResult>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  refresh: () => apiFetch<AuthTokenResult>("/auth/token/refresh"),
  // 백엔드에 /auth/logout이 아직 없다 — 지금은 프론트에서 accessToken만 비우면 된다 (client.ts의 setAccessToken(null)).
  me: () => apiFetch<UserInfoResult>("/users/me"),
  // [T-AUTH-7] 소셜 "약관동의+정보입력" 화면에서 '가입 완료' 시 호출한다.
  completeSocialSignup: (provider: string, payload: SocialSignupCompletePayload) =>
    apiFetch<AuthTokenResult>(`/auth/${provider}/complete-signup`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
