// src/api/endpoints/auth.ts
import axios from "axios";
import { apiClient } from "../client";
import type { SignupRequest, TokenResponse, UserMe } from "../../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export const authApi = {
  signup: (data: SignupRequest) => apiClient.post("/users/signup", data),

  checkEmail: (email: string) => apiClient.get(`/users/check-email?email=${encodeURIComponent(email)}`),

  // 로그인은 로그인 전이라 apiClient(=토큰 필요)를 안 쓰고 axios를 직접 씁니다.
  // 백엔드가 Form 데이터(username/password)를 받게 되어 있어 URLSearchParams로 감쌌습니다.
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    const res = await axios.post(`${API_BASE}/users/login`, form, {
      withCredentials: true,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return res.data;
  },

  logout: () => apiClient.post("/users/logout"),

  refresh: async (): Promise<TokenResponse> => {
    const res = await axios.post(`${API_BASE}/users/refresh`, {}, { withCredentials: true });
    return res.data;
  },

  getMe: async (): Promise<UserMe> => {
    const res = await apiClient.get("/users/me");
    return res.data;
  },
};
