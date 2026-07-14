// api_spec_core_v1_v1.1.yaml과 1:1로 수동 동기화 (FRONTEND_ARCHITECTURE.md 4번 — React Query/자동생성 대신 수동 패턴).
// 백엔드 /auth/login, /auth/token/refresh 응답: access_token만 body로 오고, refresh_token은 httpOnly 쿠키로 내려온다.
export interface AuthTokenResult {
  access_token: string;
}

// 백엔드 /auth/signup 요청 바디 (app/dtos/auth.py의 SignUpRequest와 1:1).
// [가입 최소화] 닉네임(name)+email+password만 받는다 - 성별/나이/휴대폰번호는 개인건강정보에서 나중에 받는다.
export interface SignupPayload {
  email: string;
  password: string;
  name: string;
}

// 백엔드 /users/me 응답. profile_id는 User(계정)와 분리된 Profile(개인정보)의 PK — 앞으로 만들
// 도메인(복약, 채팅 등) API를 호출할 때는 id가 아니라 이 profile_id를 기준으로 데이터를 조회/저장한다.
export interface UserInfoResult {
  id: number;
  profile_id: number;
  name: string;
  email: string;
  phone_number: string | null;
  gender: "MALE" | "FEMALE" | null;
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

// 백엔드 app/dtos/content_dto.py와 1:1로 수동 동기화 (T-LLM-3).
export type ContentCategory = "LIFESTYLE" | "FOOD" | "MEDICAL_NEWS";

export interface HealthContentResult {
  disease_code: string;
  category: ContentCategory;
  content_date: string; // YYYY-MM-DD
  title: string;
  summary: string;
  body: string;
  image_prompt: string | null;
  disclaimer: string;
}

export interface ContentsFeedResult {
  // false면 비로그인/질환 미등록으로 전체 콘텐츠를 폴백한 결과 — "질환 등록" 안내 배너 노출 기준.
  personalized: boolean;
  items: HealthContentResult[];
}

// 백엔드 app/dtos/health_info.py와 1:1로 수동 동기화. 더보기 > 개인건강정보.
export type Disease =
  "CANCER" | "HEART_DISEASE" | "CEREBROVASCULAR_DISEASE" | "DIABETES" | "LIVER_DISEASE" | "OTHER";

export type DiseaseStatus = "WELL_CONTROLLED" | "MODERATE" | "UNCONTROLLED" | "CURED";

export type FamilyRelation = "PARENT" | "SIBLING" | "GRANDPARENT" | "OTHER";

// 본인 진단병력 항목 하나. disease_subtype(구체적 질환명, 예: "폐암")은 AI가 약물/관리법을
// 판단하는 데 대분류(disease)만으론 부족해서 따로 받는다. 나머지는 전부 선택.
export interface DiagnosisEntry {
  disease: Disease;
  disease_subtype: string | null;
  diagnosed_years_ago: number | null;
  status: DiseaseStatus | null;
  on_medication: boolean | null;
  detail: string | null;
}

// 가족력 항목 하나. relation(혈연관계)은 유전적 위험도 해석에 직접 영향을 주므로 구조화해서 받는다.
export interface FamilyHistoryEntry {
  disease: Disease;
  disease_subtype: string | null;
  relation: FamilyRelation | null;
  detail: string | null;
}

export interface DiseaseSubtypeSearchResult {
  name: string;
  is_custom: boolean;
}

export interface HealthInfoResult {
  // [변경] 가입 시 나이/성별을 안 받아서, 여기가 나이/성별을 처음 입력받는 곳이 됐다 (둘 다 수정 가능).
  // [재설계] 나이는 저장하지 않고 birth_date(생년월일, 연도 포함)로부터 항상 자동 계산된다
  // (카카오 비즈앱 전환 후 실제 생년월일을 받아올 가능성을 고려한 결정).
  age: number | null; // birth_date로 계산된 만 나이, birth_date 없으면 null
  birth_date: string | null; // "YYYY-MM-DD" 형식
  gender: "MALE" | "FEMALE" | null;
  height_cm: number | null;
  weight_kg: number | null;
  bmi: number | null; // height_cm/weight_kg 둘 다 있어야 값이 있음, 백엔드가 계산해서 내려줌
  diagnosis_history: DiagnosisEntry[];
  family_history: FamilyHistoryEntry[];
  special_notes: string | null;
  other_notes: string | null;
}

// PATCH 요청 바디. 전부 선택 - 보낸 필드만 반영된다. 빈 배열([])을 보내면 "질병 없음"으로 확정되어 지워진다.
export interface HealthInfoUpdatePayload {
  birth_date?: string; // "YYYY-MM-DD"
  gender?: "MALE" | "FEMALE";
  height_cm?: number;
  weight_kg?: number;
  diagnosis_history?: DiagnosisEntry[];
  family_history?: FamilyHistoryEntry[];
  special_notes?: string;
  other_notes?: string;
}

// PATCH /users/me 요청 바디. email은 로그인 식별자라 백엔드가 애초에 안 받는다(가입 후 고정).
export interface UserUpdatePayload {
  name?: string;
  phone_number?: string;
  gender?: "MALE" | "FEMALE";
}
