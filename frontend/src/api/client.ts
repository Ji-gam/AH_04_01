// src/api/client.ts
// [starter] 공유 구역(api/)입니다. 백엔드 주소가 바뀌면 이 파일의 baseURL만 고치면 됩니다.
// 백엔드는 OZ코딩스쿨 템플릿 기준(app/apis/v1/auth.py 등)이고, /api/v1 접두사가 붙습니다.
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../store/authStore";

export const apiClient = axios.create({
  // [핀포인트 수정] 프론트(localhost:5173)와 백엔드(127.0.0.1:8000)는 서로 다른 origin이라도 괜찮습니다.
  // 소셜로그인(구글 등) 콜백이 실제로 이동하는 주소가 127.0.0.1:8000이라, 여기도 반드시 그 주소로
  // 통일해야 쿠키가 같은 origin 것으로 인식됩니다. 백엔드 main.py의 CORS 설정이 이 프론트 주소를
  // 허용하고 있어야 합니다 (allow_credentials=True 필수).
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1",
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
      return new Promise((resolve) => {
        pendingQueue.push(() => resolve(apiClient(originalRequest)));
      });
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      // 백엔드는 GET /auth/token/refresh 입니다 (POST 아님 — 예전 버전과 다른 부분).
      const res = await apiClient.get("/auth/token/refresh");
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
