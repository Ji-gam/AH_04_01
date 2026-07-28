import { apiFetch, apiFetchRaw } from "./client";
import type { AuthTokenResult, SignupPayload, UserInfoResult, UserUpdatePayload } from "./types";

/** 소셜 로그인 시작 주소. <a href>로 브라우저를 그대로 이동시키는 용도 (fetch 아님 - OAuth는 리다이렉트라서 fetch로 못 함). */
export function socialLoginUrl(provider: "google" | "kakao" | "naver"): string {
  return `/api/v1/auth/${provider}/login`;
}

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
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  logout: async () => {
    await apiFetchRaw("/auth/logout", { method: "POST" });
  },
  me: () => apiFetch<UserInfoResult>("/users/me"),
  updateMe: (payload: UserUpdatePayload) =>
    apiFetch<UserInfoResult>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  // 204 No Content라 JSON 바디가 없다 — apiFetch(res.json())를 쓰면 파싱 에러가 나서 raw fetch를 쓴다.
  // (2026-07-28) 소셜 가입자는 비밀번호가 없어서 password를 아예 안 보내도 되게 선택값으로 변경.
  withdraw: async (password?: string) => {
    await apiFetchRaw("/auth/withdraw", {
      method: "DELETE",
      body: JSON.stringify({ password: password ?? null }),
    });
  },
};
