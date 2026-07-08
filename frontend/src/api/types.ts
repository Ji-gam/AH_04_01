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
  created_at: string;
}

export interface ChatSessionCreateResult {
  session_id: string;
}

// 백엔드 app/dtos/notifications.py와 1:1로 수동 동기화.
export type FrequencyType = "DAILY" | "WEEKLY";
export type DayOfWeek = "일" | "월" | "화" | "수" | "목" | "금" | "토";

export interface NotificationScheduleResult {
  id: number;
  medication_name: string;
  frequency_type: FrequencyType;
  target_day_of_week: DayOfWeek | null;
  alarm_time: string; // "HH:MM:SS"
  is_active: boolean;
}

export interface NotificationScheduleCreateRequest {
  medication_name: string;
  frequency_type: FrequencyType;
  target_day_of_week?: DayOfWeek | null;
  alarm_time: string;
}

export interface NotificationScheduleUpdateRequest {
  medication_name?: string;
  frequency_type?: FrequencyType;
  target_day_of_week?: DayOfWeek | null;
  alarm_time?: string;
  is_active?: boolean;
}

// ChatMessageChunk 스키마 (api_spec_core_v1.yaml). text/plain 스트림의 각 줄이 이 형태의 JSON이다.
export interface ChatMessageChunk {
  type: "token" | "emergency_fallback" | "done";
  content: string;
  disclaimer?: string;
}

export interface ChatSessionResponse {
  id: number;
  created_at: string;
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}
