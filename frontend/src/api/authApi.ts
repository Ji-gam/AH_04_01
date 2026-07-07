import { apiFetch } from "./client";
import type { AuthTokenResult, SignupPayload, UserInfoResult } from "./types";

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
};
