// src/store/authStore.ts
// [starter] 공유 구역(store/)입니다. 다른 도메인 상태는 별도 파일로 추가하면 됩니다.
// access_token은 일부러 localStorage에 안 넣습니다 (XSS 탈취 위험 때문에 메모리에만 둠).
// 새로고침하면 사라지는데, App.tsx가 시작할 때 refresh_token 쿠키로 자동 복구합니다.
import { create } from "zustand";
import type { CurrentUser } from "../types/auth";

interface AuthState {
  accessToken: string | null;
  user: CurrentUser | null;
  isAuthReady: boolean;
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
