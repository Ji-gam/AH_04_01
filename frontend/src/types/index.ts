// src/types/index.ts
// backend/domains/*/schema.py 와 1:1로 대응하는 타입입니다.
// 백엔드 스키마가 바뀌면 여기도 같이 고쳐주세요 (자동 동기화 아님, 수동 관리).

// ---------- [M1] Auth / User ----------
export interface SignupRequest {
  email: string;
  password?: string;
  name: string;
  role_type?: "PATIENT" | "GUARDIAN";
  gender?: string;
  birth_date?: string;
  sns_provider?: "LOCAL" | "GOOGLE";
  sns_id?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserMe {
  user_id: number;
  email: string;
  name: string;
  role_type: "PATIENT" | "GUARDIAN";
  gender?: string;
  birth_date?: string;
  use_voice_mode: boolean;
  use_large_font: boolean;
  wake_time?: string;
  breakfast_time?: string;
  lunch_time?: string;
  dinner_time?: string;
  bed_time?: string;
}

// ---------- [M2] PWA Subscription ----------
export interface SubscriptionCreate {
  endpoint_url: string;
  p256dh_key: string;
  auth_key: string;
}

// ---------- [M3] Support Group ----------
export interface GroupCreateResponse {
  group_id: number;
  group_name: string;
  invite_code: string;
  created_at: string;
}

export interface GroupMemberResponse {
  member_id: number;
  user_id: number;
  name: string;
  leaderboard_score: number;
  joined_at: string;
}

// ---------- [M4] Emergency Card ----------
export interface EmergencyCard {
  card_id: number;
  user_id: number;
  blood_type?: string;
  food_allergies?: string;
  medication_allergies?: string;
  past_history?: string;
  present_history?: string;
  family_history?: string;
  emergency_contacts?: string;
}

// ---------- [M5] Medical Record / Medication ----------
export interface MedicationMapping {
  mapping_id: number;
  medication_id: number;
  medication_name: string;
  dosage_per_take?: string;
  takes_per_day?: number;
  duration_days?: number;
  instruction?: string;
  device_type?: "MULTI_DOSE_PEN" | "SINGLE_USE_PEN" | "TABLET";
  total_clicks_or_doses?: number;
  total_prescribed_quantity?: number;
  remaining_quantity?: number;
}

export interface RecordDetail {
  record_id: number;
  document_type?: string;
  hospital_name?: string;
  pharmacy_name?: string;
  diagnosis_name?: string;
  diagnosis_code?: string;
  visit_date?: string;
  receipt_amount?: number;
  medications: MedicationMapping[];
}

export interface Medication {
  medication_id: number;
  standard_code?: string;
  medication_name: string;
  form_type?: string;
  dosage_guideline?: string;
  side_effects?: string;
  precautions?: string;
  storage_method?: string;
}

// ---------- [M6] Schedule / Intake Log ----------
export interface ScheduleCreate {
  medication_id: number;
  record_id?: number;
  card_alias?: string;
  frequency_type: "DAILY" | "WEEKLY";
  target_day_of_week?: string;
  alarm_time: string; // "HH:MM:SS"
}

export interface Schedule {
  schedule_id: number;
  medication_id: number;
  record_id?: number;
  card_alias?: string;
  frequency_type: "DAILY" | "WEEKLY";
  target_day_of_week?: string;
  alarm_time: string;
  is_active: boolean;
}

export interface IntakeLog {
  log_id: number;
  schedule_id: number;
  card_alias?: string;
  planned_date: string;
  actual_take_time?: string;
  status: "COMPLETED" | "MISSED";
  verification_media_url?: string;
}

// ---------- [M7] Food Intake ----------
export interface FoodIntakeCreate {
  meal_time_type: "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK";
  food_name: string;
  image_url?: string;
  calories?: number;
  sugar_content?: number;
}

// ---------- [M8] Drug-Food Interaction ----------
export interface InteractionRule {
  interaction_id: number;
  medication_id: number;
  substance_name: string;
  risk_level: "INFO" | "WARNING" | "DANGER";
  guidance_text?: string;
}

// ---------- [M9] Health Metric / Appointment / Symptom ----------
export interface HealthMetricCreate {
  weight?: number;
  height?: number;
  blood_pressure_systolic?: number;
  blood_pressure_diastolic?: number;
  blood_glucose?: number;
}

export interface AppointmentCreate {
  hospital_name: string;
  doctor_name?: string;
  doctor_contact?: string;
  appointment_at: string;
  memo?: string;
}

export interface SymptomLogCreate {
  symptom_notes: string;
  severity_level: number;
}

// ---------- [M10] Chat / Generated Guide ----------
export interface ChatSession {
  session_id: number;
  user_id: number;
  session_title?: string;
  session_intent_mode: "DIET_ASSIST" | "PARENT_MONITOR";
  has_injected_context: boolean;
  created_at: string;
}

export interface ChatMessage {
  message_id: number;
  sender_type: "USER" | "ASSISTANT";
  message_text: string;
}

export interface GeneratedGuide {
  guide_id: number;
  user_id: number;
  record_id?: number;
  guide_type: string;
  content?: string;
  created_at: string;
}
