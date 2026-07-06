// src/api/client.ts
// 모든 API 호출이 거쳐가는 axios 인스턴스입니다.
// - 요청마다 Authorization: Bearer <access_token> 을 자동으로 붙여줍니다.
// - 401(토큰 만료)이 오면 자동으로 /users/refresh 를 호출해서 새 토큰을 받고,
//   원래 요청을 한 번 재시도합니다. (사용자는 로그인이 끊긴 걸 거의 못 느낌)
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/authStore";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  withCredentials: true, // refresh_token 쿠키를 주고받기 위해 필수
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let pendingQueue: Array<() => void> = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      // 이미 다른 요청이 갱신 중이면, 갱신이 끝날 때까지 기다렸다가 재시도합니다.
      return new Promise((resolve) => {
        pendingQueue.push(() => resolve(apiClient(originalRequest)));
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const res = await axios.post(
        `${import.meta.env.VITE_API_BASE_URL || "/api/v1"}/users/refresh`,
        {},
        { withCredentials: true }
      );
      const newToken = res.data.access_token as string;
      useAuthStore.getState().setAccessToken(newToken);

      pendingQueue.forEach((cb) => cb());
      pendingQueue = [];

      return apiClient(originalRequest);
    } catch (refreshError) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);
