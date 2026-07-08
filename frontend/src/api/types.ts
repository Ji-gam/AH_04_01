// [T-AUTH-7] 약관동의 항목. service_terms/privacy/sensitive_info는 필수, marketing은 선택.
// 개인정보보호법 제23조(민감정보는 다른 개인정보 처리 동의와 별도로 받아야 함)를 반영해
// sensitive_info를 privacy와 분리된 항목으로 둔다.
export interface AgreementPayload {
  service_terms: boolean;
  privacy: boolean;
  sensitive_info: boolean;
  marketing: boolean;
}

// api_spec_core_v1_v1.1.yaml과 1:1로 수동 동기화 (FRONTEND_ARCHITECTURE.md 4번 — React Query/자동생성 대신 수동 패턴).
// 백엔드 /auth/login, /auth/token/refresh 응답: access_token만 body로 오고, refresh_token은 httpOnly 쿠키로 내려온다.
export interface AuthTokenResult {
  access_token: string;
}
// 백엔드 /auth/signup 요청 바디 (app/dtos/auth.py의 SignUpRequest와 1:1).
export interface SignupPayload {
  email: string;
  password: string;
  name: string;
  gender: "MALE" | "FEMALE";
  birth_date: string; // YYYY-MM-DD
  phone_number: string;
  agreements: AgreementPayload;
}
// 백엔드 /users/me 응답. profile_id는 User(계정)와 분리된 Profile(개인정보)의 PK — 앞으로 만들
// 도메인(복약, 채팅 등) API를 호출할 때는 id가 아니라 이 profile_id를 기준으로 데이터를 조회/저장한다.
export interface UserInfoResult {
  id: number;
  profile_id: number;
  name: string;
  email: string;
  phone_number: string;
  birthday: string;
  gender: "MALE" | "FEMALE";
  height_cm: number | null;
  weight_kg: number | null;
  diagnosis_history: Disease[];
  family_history: Disease[];
  health_notes: string | null;
  created_at: string;
}
export interface ChatSessionCreateResult {
  session_id: string;
}
// ChatMessageChunk 스키마 (api_spec_core_v1.yaml). text/plain 스트림의 각 줄이 이 형태의 JSON이다.
export interface ChatMessageChunk {
  type: "token" | "emergency_fallback" | "done";
  content: string;
  disclaimer?: string;
}

// 백엔드 POST /auth/{provider}/complete-signup 요청 바디.
// 소셜 로그인은 이름/이메일만 주므로, 성별/생년월일/휴대폰번호는 이 화면에서 직접 입력받는다.
export interface SocialSignupCompletePayload {
  pending_token: string;
  name: string;
  gender: "MALE" | "FEMALE";
  birth_date: string; // YYYY-MM-DD
  phone_number: string;
  agreements: AgreementPayload;
}

// [T-PROFILE-1] 5대질환: 암/심장질환/뇌혈관질환/당뇨/간질환.
export type Disease = "CANCER" | "HEART_DISEASE" | "CEREBROVASCULAR_DISEASE" | "DIABETES" | "LIVER_DISEASE";

// 백엔드 PATCH /users/me/biometric-info 요청 바디. 전달 안 한 필드는 기존 값 유지(부분 수정).
export interface BiometricInfoPayload {
  height_cm: number;
  weight_kg: number;
  diagnosis_history: Disease[];
  family_history: Disease[];
  health_notes: string;
}

// 백엔드 PATCH /users/me 요청 바디. 전달 안 한 필드는 기존 값 유지(부분 수정).
export interface UserUpdatePayload {
  name: string;
  email: string;
  phone_number: string;
  birthday: string; // YYYY-MM-DD
  gender: "MALE" | "FEMALE";
}

// 백엔드 DELETE /auth/withdraw 요청 바디. LOCAL 계정만 password 필요.
export interface WithdrawPayload {
  password?: string;
}
