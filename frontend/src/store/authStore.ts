// src/store/authStore.ts
// 로그인 상태(access token, 유저 정보)를 앱 전체에서 공유하는 스토어입니다.
// ⚠️ access_token은 새로고침하면 사라집니다 (의도된 동작). 새로고침 시 App.tsx가
// /users/refresh를 한 번 호출해서 쿠키 기반으로 다시 토큰을 받아옵니다.
import { create } from "zustand";

export interface CurrentUser {
  user_id: number;
  email: string;
  name: string;
  role_type: "PATIENT" | "GUARDIAN";
}

interface AuthState {
  accessToken: string | null;
  user: CurrentUser | null;
  isAuthReady: boolean; // 앱 시작 시 refresh 시도가 끝났는지 여부
  setAccessToken: (token: string) => void;
  setUser: (user: CurrentUser | null) => void;
  setAuthReady: (ready: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  isAuthReady: false,
  setAccessToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),
  setAuthReady: (ready) => set({ isAuthReady: ready }),
  logout: () => set({ accessToken: null, user: null }),
}));
