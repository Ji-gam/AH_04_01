import { apiFetch } from "./client";
import type { BiometricInfoPayload, UserInfoResult, UserUpdatePayload, WithdrawPayload } from "./types";

export const userApi = {
  // [T-PROFILE-1] 회원가입 직후 "생체정보 입력" 화면에서 호출한다. 부분 수정 방식이라
  // 값을 안 보낸 필드는 그대로 유지된다 (전체 필드를 강제하지 않음 - 건너뛰기 가능).
  updateBiometricInfo: (payload: Partial<BiometricInfoPayload>) =>
    apiFetch<UserInfoResult>("/users/me/biometric-info", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  // 계정설정 화면에서 이름/이메일/전화번호/생일/성별을 부분 수정한다.
  updateProfile: (payload: Partial<UserUpdatePayload>) =>
    apiFetch<UserInfoResult>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

export const accountApi = {
  // [T-AUTH-8] LOCAL 계정은 password 필수, 소셜 계정은 생략 가능(빈 객체로 호출).
  withdraw: (payload: WithdrawPayload) =>
    apiFetch<{ detail: string }>("/auth/withdraw", {
      method: "DELETE",
      body: JSON.stringify(payload),
    }),
};
