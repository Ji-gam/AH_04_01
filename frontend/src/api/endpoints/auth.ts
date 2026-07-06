// src/api/endpoints/auth.ts
// 담당 도메인: auth. 백엔드 계약(오늘 실제 브라우저로 검증 완료)에 맞춰 작성했습니다.
import { apiClient } from "../client";
import type { LoginRequest, LoginResponse, SignupRequest, CurrentUser, SocialProvider } from "../../types/auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export const authApi = {
  signup: (data: SignupRequest) => apiClient.post("/auth/signup", data),

  // ⚠️ 로그인은 Form이 아니라 JSON body 입니다 (예전 SQLAlchemy 버전과 다른 부분).
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const res = await apiClient.post("/auth/login", data);
    return res.data;
  },

  logout: () => apiClient.post("/auth/logout"),

  // ⚠️ 재발급은 GET 입니다 (POST 아님).
  refresh: async (): Promise<LoginResponse> => {
    const res = await apiClient.get("/auth/token/refresh");
    return res.data;
  },

  // ⚠️ 이건 엄밀히는 "users" 도메인 API라 나중에 users 담당자가 생기면
  // src/api/endpoints/users.ts로 옮기는 게 맞습니다. 지금은 로그인 직후 내 정보를
  // 화면에 보여주려면 필요해서 임시로 auth.ts에 같이 뒀습니다.
  getMe: async (): Promise<CurrentUser> => {
    const res = await apiClient.get("/users/me");
    return res.data;
  },

  // 소셜 로그인 버튼이 이동할 주소만 만들어줍니다. axios로 호출하지 않고
  // <a href={authApi.socialLoginUrl("google")}> 형태로 그냥 링크 이동시켜야 합니다.
  socialLoginUrl: (provider: SocialProvider): string => `${API_BASE}/auth/${provider}/login`,
};
