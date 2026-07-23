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

// 백엔드 app/dtos/notification_settings.py와 1:1로 수동 동기화.
export interface NotificationSettingsResult {
  push_enabled: boolean;
  chatbot_reply_enabled: boolean;
  notice_enabled: boolean;
  marketing_enabled: boolean;
  lifestyle_tip_enabled: boolean;
  quiet_mode_enabled: boolean;
  quiet_start: string; // "HH:MM:SS"
  quiet_end: string; // "HH:MM:SS"
  sound_enabled: boolean;
  vibration_enabled: boolean;
  popup_enabled: boolean;
  adherence_feedback_day_of_week: number; // 0=월 ~ 6=일 (F-ADH-2)
}

export type NotificationSettingsUpdateRequest = Partial<NotificationSettingsResult>;

// 백엔드 app/dtos/notice.py와 1:1로 수동 동기화.
export type NoticeKind = "NOTICE" | "MARKETING";

export interface NoticeResult {
  id: number;
  kind: NoticeKind;
  title: string;
  body: string;
  created_at: string;
  is_new: boolean;
}

export interface NoticeCreateRequest {
  kind: NoticeKind;
  title: string;
  body: string;
}

// T-LLM-7-3-2: 답변 생성에 쓰인 출처 각주 1건(DUR은 name만, 논문은 url도 있음).
export interface ChatSourceRef {
  name: string;
  url?: string | null;
  // RAG 유사도 스코어. 디버깅/품질 확인용 - 현재 ChatPage는 렌더링하지 않는다.
  score?: number | null;
}

// ChatMessageChunk 스키마 (api_spec_core_v1.yaml). text/plain 스트림의 각 줄이 이 형태의 JSON이다.
// 통합 RAG 스트리밍(T-LLM-7-3-2): 매 답변마다 "sources"가 먼저 도착해 새 어시스턴트
// 메시지를 열고(DUR+논문 출처 통합 목록, 없으면 빈 배열), 그 다음 "token"이 이어붙는다.
export interface ChatMessageChunk {
  type: "sources" | "token" | "emergency_fallback" | "done";
  content: string;
  disclaimer?: string;
  sources?: ChatSourceRef[];
}

export interface ChatSessionResponse {
  id: number;
  created_at: string;
}

export interface ChatMessageResponse {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSourceRef[] | null;
  disclaimer?: string | null;
  created_at: string;
}

// 백엔드 app/dtos/content_dto.py와 1:1로 수동 동기화 (T-LLM-3).
export type ContentCategory = "LIFESTYLE" | "FOOD" | "MEDICAL_NEWS";

export interface HealthContentResult {
  id: number;
  disease_code: string;
  category: ContentCategory;
  content_date: string; // YYYY-MM-DD
  title: string;
  summary: string;
  body: string;
  image_prompt: string | null;
  // 원문 출처 URL 목록(상세화면 "참고자료" 섹션용). 실제 생성 파이프라인이 아직 채우지
  // 않아 현재는 항상 null/빈 배열 — 있을 때만 섹션을 노출한다.
  source_refs: string[] | null;
  disclaimer: string;
}

export interface ContentsFeedResult {
  // false면 비로그인/질환 미등록으로 전체 콘텐츠를 폴백한 결과 — "질환 등록" 안내 배너 노출 기준.
  personalized: boolean;
  items: HealthContentResult[];
}

// 백엔드 GET /contents/{id}/related 응답과 1:1 수동 동기화 (T-LLM-3-1). 같은 disease_code,
// 다른 category, 자기 자신 제외 최신순 최대 limit개.
export interface RelatedContentResult {
  items: HealthContentResult[];
}

// [QA 전용] POST /contents/generate 요청 바디. 전부 생략 가능 - 생략 시 서버가 무작위로 고른다.
export interface GenerateContentPayload {
  disease_code?: string;
  category?: ContentCategory;
  topic?: string;
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
  // [#71 해결] 채팅 임부금기 DUR 경고 실연동용. 선택 입력 - 미입력이면 null.
  is_pregnant: boolean | null;
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
  is_pregnant?: boolean;
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

// 백엔드 app/dtos/habit.py와 1:1로 수동 동기화. 홈 화면 습관 트래커.
export interface HabitItemResult {
  key: string;
  label: string;
  icon: string;
  unit: string;
  target: number;
  progress: number;
  completed: boolean;
}

export interface HabitsTodayResult {
  habits: HabitItemResult[];
  all_completed: boolean;
}

export interface HabitRecommendationItemResult {
  key: string;
  label: string;
  icon: string;
  unit: string;
  target: number;
}

export interface HabitRecommendationsResult {
  habits: HabitRecommendationItemResult[];
  selected_keys: string[];
}

// 백엔드 app/dtos/dur_dto.py와 1:1로 수동 동기화 (T-MED-14). 처방/약품명 배열을 넣으면 DUR(의약품
// 안전사용) 정보를 3단계로 내려주는 스크리닝 API. drug_names만 보내면 되고 로그인 불필요.

/** 다른 약을 이름 문자열이 아니라 item_seq로 참조 - 이름 재매칭 없이 상세로 바로 링크 가능. */
export interface DurDrugRef {
  item_seq: string;
  item_name: string;
}

/** 항상 6개 고정 순서(PWNM/ODSN/SPCIFY_AGRDE/MDCTN/SEOBANG/CPCTY)로 내려온다 - "없으면 표시 안
 * 함" 판단 없이 그대로 pill 6개에 매핑하면 된다. */
export interface DurSimpleFlag {
  rule_code: "PWNM" | "ODSN" | "SPCIFY_AGRDE" | "MDCTN" | "SEOBANG" | "CPCTY";
  rule_label: string;
  present: boolean;
  prohbt_content: string | null;
  remark: string | null;
}

export interface DurDrugIdentification {
  shape: string | null;
  color: string | null;
  mark: string | null;
}

export interface DurDrugDetail {
  item_seq: string;
  item_name: string;
  entp_name: string | null;
  etc_otc_name: string | null;
  form_name: string | null;
  efcy_qesitm: string | null;
  use_method_qesitm: string | null;
  atpn_warn_qesitm: string | null;
  se_qesitm: string | null;
  deposit_method_qesitm: string | null;
  item_image: string | null;
  identification: DurDrugIdentification | null;
  // T-MED-14-1: DrugPrdtPrmsnInfoService07(품목당 성분 상세) 기반 추가 정보.
  atc_code: string | null;
  is_rare_drug: boolean | null;
  narcotic_kind_name: string | null; // "마약"/"향정"/"한외마약" 등, 해당 없으면 null
}

export interface DurBasicScreeningResult {
  drug_detail: DurDrugDetail;
  dur_simple: DurSimpleFlag[];
}

export interface DurBasicScreeningResponse {
  results: DurBasicScreeningResult[];
  unmatched_drug_names: string[];
}

export interface DurInteractionWarning {
  rule_type: string; // "병용금기" | "효능군중복주의"
  drug_a: DurDrugRef;
  drug_b: DurDrugRef;
  prohbt_content: string | null;
  remark: string | null;
}

export interface DurRecallInfo {
  item_seq: string;
  item_name: string;
  entp_name: string | null;
  recall_reason: string | null;
  recall_command_date: string | null;
  enforced: boolean | null;
}

export interface DurInteractionScreeningResponse {
  drug_intrc: {
    interactions: DurInteractionWarning[];
    recalls: DurRecallInfo[];
  };
  unmatched_drug_names: string[];
}

export interface DurIngredientRuleDetail {
  rule_type: string;
  prohbt_content: string | null;
  remark: string | null;
  /** 규칙별 부가 수치/등급 (임부금기=등급, 특정연령대금기=연령 기준, 용량주의=최대 1일 용량,
   * 투여기간주의=최대 투여기간, 해당 없으면 null) */
  rule_detail: string | null;
}

/** 이 성분을 가진 입력 약품 - item_seq로 상세화면 링크 가능, qnt/unit은 이 약에서의 실제 함량
 * (drug_prdt_mcpn_detail 기반일 때만 채워짐, MATERIAL_NAME 텍스트 폴백이면 null). */
export interface DurIngredientSourceDrug {
  item_seq: string;
  item_name: string;
  qnt: string | null;
  unit: string | null;
}

export interface DurIngredientDetail {
  ingr_code: string;
  ingr_name: string;
  source_drugs: DurIngredientSourceDrug[];
  rules: DurIngredientRuleDetail[];
}

export interface DurIngredientScreeningResponse {
  ingredients: DurIngredientDetail[];
  unmatched_drug_names: string[];
}
